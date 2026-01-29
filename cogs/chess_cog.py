# cogs/chess_cog.py

import discord
from discord.ext import commands
from discord import app_commands
from io import BytesIO
import chess
import chess.svg
import cairosvg
from typing import Optional
import random
from discord import ui
from discord import SelectOption

# --- L'INTERFACE DE JEU ---
class GameView(ui.View):
    def __init__(self, game_board: chess.Board, white_player: discord.Member, black_player: discord.Member):
        super().__init__(timeout=None)
        self.board = game_board
        self.white_player = white_player
        self.black_player = black_player
        self.selected_square: Optional[int] = None
        self.ability_piece_type: Optional[chess.PieceType] = None
        self.mind_control_target: Optional[int] = None
        self.create_selection_interface()

    def create_selection_interface(self):
        self.clear_items(); self.selected_square = None
        self.ability_piece_type = None; self.mind_control_target = None
        file_options = [discord.SelectOption(label=chr(ord('a') + i), value=str(i)) for i in range(8)]
        self.add_item(Dropdown(placeholder="Colonne...", options=file_options, custom_id="file_select"))
        rank_options = [discord.SelectOption(label=str(i + 1), value=str(i)) for i in range(8)]
        self.add_item(Dropdown(placeholder="Rangée...", options=rank_options, custom_id="rank_select"))
        self.add_item(Button(label="Sélectionner", style=discord.ButtonStyle.primary, custom_id="select_piece_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_action_interface(self, square: int):
        self.clear_items(); self.selected_square = square
        piece = self.board.piece_at(square)
        self.add_item(Button(label="Se déplacer", style=discord.ButtonStyle.secondary, custom_id="show_moves_btn"))
        if piece.piece_type == chess.KING: self.add_item(Button(label="Balayage Royal 👑", style=discord.ButtonStyle.success, custom_id="royal_sweep_btn"))
        elif piece.piece_type == chess.KNIGHT: self.add_item(Button(label="Double Assaut ⚔️", style=discord.ButtonStyle.success, custom_id="double_assault_start_btn"))
        elif piece.piece_type == chess.BISHOP: self.add_item(Button(label="Téléportation ✨", style=discord.ButtonStyle.success, custom_id="teleport_start_btn"))
        elif piece.piece_type == chess.ROOK: self.add_item(Button(label="Équipe de secours 🛡️", style=discord.ButtonStyle.success, custom_id="rescue_team_start_btn"))
        elif piece.piece_type == chess.QUEEN: self.add_item(Button(label="Contrôle mental 🧠", style=discord.ButtonStyle.success, custom_id="mind_control_start_btn"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.danger, row=2, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_destination_interface(self, from_square: int, possible_moves: list[int]):
        self.clear_items(); self.selected_square = from_square
        move_options = [discord.SelectOption(label=chess.square_name(sq), value=str(sq)) for sq in possible_moves]
        self.add_item(Dropdown(placeholder="Destination...", options=move_options, custom_id="destination_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_double_assault_interface(self, from_square: int, possible_moves: list[int], step: int):
        self.clear_items(); self.selected_square = from_square
        placeholder = "Première destination..." if step == 1 else "Seconde destination..."
        custom_id = "double_assault_move1_select" if step == 1 else "double_assault_move2_select"
        move_options = [discord.SelectOption(label=chess.square_name(sq), value=str(sq)) for sq in possible_moves]
        self.add_item(Dropdown(placeholder=placeholder, options=move_options, custom_id=custom_id))
        cancel_custom_id = "cancel_btn" if step == 1 else "cancel_ability_btn"
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id=cancel_custom_id))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_teleport_target_interface(self):
        self.clear_items()
        white_options = []; black_options = []
        for square, piece in self.board.piece_map().items():
            piece_name = chess.piece_name(piece.piece_type).capitalize(); label = f"{piece_name} en {chess.square_name(square)}"
            option = discord.SelectOption(label=label, value=str(square))
            if piece.color == chess.WHITE: white_options.append(option)
            else: black_options.append(option)
        if white_options: self.add_item(Dropdown(placeholder="Cibler une pièce Blanche...", options=white_options, custom_id="teleport_target_white_select"))
        if black_options: self.add_item(Dropdown(placeholder="Cibler une pièce Noire...", options=black_options, custom_id="teleport_target_black_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_teleport_destination_interface(self, target_square: int, possible_destinations: list[int]):
        self.clear_items()
        move_options = [discord.SelectOption(label=chess.square_name(sq), value=str(sq)) for sq in possible_destinations]
        self.add_item(Dropdown(placeholder="Choisissez la case d'atterrissage...", options=move_options, custom_id="teleport_destination_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_rescue_team_piece_select_interface(self, piece_options: list[discord.SelectOption]):
        self.clear_items()
        self.add_item(Dropdown(placeholder="Quelle pièce capturée ramener ?", options=piece_options, custom_id="rescue_team_piece_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_rescue_team_destination_interface(self, destination_options: list[discord.SelectOption]):
        self.clear_items()
        self.add_item(Dropdown(placeholder="Où la placer ?", options=destination_options, custom_id="rescue_team_destination_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_mind_control_target_interface(self, target_options: list[discord.SelectOption]):
        self.clear_items()
        self.add_item(Dropdown(placeholder="Quelle pièce ennemie contrôler ?", options=target_options, custom_id="mind_control_target_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    def create_mind_control_destination_interface(self, destination_options: list[discord.SelectOption]):
        self.clear_items()
        self.add_item(Dropdown(placeholder="Quel coup forcer ?", options=destination_options, custom_id="mind_control_destination_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
    async def generate_board_image(self, **kwargs) -> discord.File:
        svg_board = chess.svg.board(board=self.board, **kwargs)
        png_board = cairosvg.svg2png(bytestring=svg_board.encode('utf-8'))
        return discord.File(fp=BytesIO(png_board), filename="echiquier.png")
    def disable_all_items(self):
        for item in self.children: item.disabled = True; self.stop()
        

# --- COMPOSANTS D'INTERFACE ---
class Dropdown(ui.Select):
    async def callback(self, interaction: discord.Interaction):
        view: GameView = self.view
        current_player = view.white_player if view.board.turn == chess.WHITE else view.black_player
        if interaction.user != current_player:
            await interaction.response.send_message("Ce n'est pas votre tour de jouer !", ephemeral=True)
            return
        from_square = view.selected_square
        if self.custom_id == "destination_select":
            to_square = int(self.values[0]); move = chess.Move(from_square, to_square)
            view.board.push(move)
            if not view.board.king(chess.WHITE) or not view.board.king(chess.BLACK):
                winner = "Noirs" if not view.board.king(chess.WHITE) else "Blancs"
                view.disable_all_items(); final_image = await view.generate_board_image()
                await interaction.response.edit_message(content=f"**Partie terminée ! Le roi a été capturé. Victoire des {winner} !**", attachments=[final_image], view=view)
                return
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Coup joué ! C'est au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "double_assault_move1_select":
            to_square = int(self.values[0]); move = chess.Move(from_square, to_square)
            view.board.push(move); view.board.turn = not view.board.turn
            if not view.board.king(chess.WHITE) or not view.board.king(chess.BLACK):
                winner = "Noirs" if not view.board.king(chess.WHITE) else "Blancs"
                view.disable_all_items(); final_image = await view.generate_board_image()
                await interaction.response.edit_message(content=f"**Partie terminée ! Le roi a été capturé. Victoire des {winner} !**", attachments=[final_image], view=view)
                return
            new_from_square = to_square
            possible_moves = [m.to_square for m in view.board.pseudo_legal_moves if m.from_square == new_from_square]
            view.create_double_assault_interface(new_from_square, possible_moves, step=2)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"
            fill_colors = dict.fromkeys(chess.SquareSet(possible_moves), moves_color); fill_colors[new_from_square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content=f"Premier coup joué ! Choisissez la seconde destination pour le cavalier en **{chess.square_name(new_from_square)}**.", attachments=[new_image], view=view)
        elif self.custom_id == "double_assault_move2_select":
            to_square = int(self.values[0]); move = chess.Move(from_square, to_square)
            view.board.push(move)
            if not view.board.king(chess.WHITE) or not view.board.king(chess.BLACK):
                winner = "Noirs" if not view.board.king(chess.WHITE) else "Blancs"
                view.disable_all_items(); final_image = await view.generate_board_image()
                await interaction.response.edit_message(content=f"**Partie terminée ! Le roi a été capturé. Victoire des {winner} !**", attachments=[final_image], view=view)
                return
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Double Assaut terminé ! C'est au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id in ["teleport_target_white_select", "teleport_target_black_select"]:
            target_square = int(self.values[0])
            neighbor_squares = chess.SquareSet(chess.BB_KING_ATTACKS[target_square])
            possible_destinations = [sq for sq in neighbor_squares if view.board.piece_at(sq) is None]
            if not possible_destinations:
                await interaction.response.send_message("Il n'y a aucune case d'atterrissage VIDE autour de cette pièce.", ephemeral=True); return
            view.create_teleport_destination_interface(target_square, possible_destinations)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"; target_color = "#ff4500aa"
            fill_colors = dict.fromkeys(chess.SquareSet(possible_destinations), moves_color)
            fill_colors[from_square] = selection_color; fill_colors[target_square] = target_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content="Cible sélectionnée. Choisissez une case d'atterrissage.", attachments=[new_image], view=view)
        elif self.custom_id == "teleport_destination_select":
            to_square = int(self.values[0])
            bishop_piece = view.board.remove_piece_at(from_square)
            view.board.set_piece_at(to_square, bishop_piece)
            view.board.push(chess.Move.null())
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Téléportation réussie ! C'est au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "rescue_team_piece_select":
            view.ability_piece_type = int(self.values[0])
            rook_square = from_square
            neighbor_squares = chess.SquareSet(chess.BB_KING_ATTACKS[rook_square])
            empty_squares = [sq for sq in neighbor_squares if view.board.piece_at(sq) is None]
            if not empty_squares:
                await interaction.response.send_message("Il n'y a aucune case vide autour de votre tour pour placer la pièce.", ephemeral=True); return
            destination_options = [discord.SelectOption(label=chess.square_name(sq), value=str(sq)) for sq in empty_squares]
            view.create_rescue_team_destination_interface(destination_options)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"
            fill_colors = dict.fromkeys(chess.SquareSet(empty_squares), moves_color); fill_colors[rook_square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content="Pièce choisie. Maintenant, sélectionnez une case vide pour la faire revenir.", attachments=[new_image], view=view)
        elif self.custom_id == "rescue_team_destination_select":
            to_square = int(self.values[0])
            new_piece = chess.Piece(view.ability_piece_type, view.board.turn)
            view.board.set_piece_at(to_square, new_piece)
            view.board.push(chess.Move.null())
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Équipe de secours réussie ! Un(e) {chess.piece_name(new_piece.piece_type)} est de retour ! Au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "mind_control_target_select":
            target_square = int(self.values[0])
            view.mind_control_target = target_square
            view.board.turn = not view.board.turn
            possible_moves = [m for m in view.board.legal_moves if m.from_square == target_square]
            view.board.turn = not view.board.turn
            if not possible_moves:
                await interaction.response.send_message("Cette pièce ennemie ne peut effectuer aucun coup légal.", ephemeral=True); return
            destination_options = [discord.SelectOption(label=view.board.san(m), value=m.uci()) for m in possible_moves]
            view.create_mind_control_destination_interface(destination_options)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"; target_color = "#ff4500aa"
            fill_colors = dict.fromkeys([m.to_square for m in possible_moves], moves_color)
            fill_colors[from_square] = selection_color; fill_colors[target_square] = target_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content="Pièce ennemie sous contrôle. Quel coup désastreux allez-vous la forcer à jouer ?", attachments=[new_image], view=view)
        elif self.custom_id == "mind_control_destination_select":
            move_uci = self.values[0]
            forced_move = chess.Move.from_uci(move_uci)
            view.board.turn = not view.board.turn; view.board.push(forced_move); view.board.turn = not view.board.turn
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Contrôle mental réussi ! Le coup forcé a été joué. C'est maintenant au tour de {next_player_mention}.", attachments=[new_image], view=view)
        else: await interaction.response.defer()

class Button(ui.Button):
    async def callback(self, interaction: discord.Interaction):
        view: GameView = self.view
        current_player = view.white_player if view.board.turn == chess.WHITE else view.black_player
        if interaction.user != current_player:
            await interaction.response.send_message("Ce n'est pas votre tour de jouer !", ephemeral=True)
            return
        square = view.selected_square
        if self.custom_id == "select_piece_btn":
            file_val = next((child.values[0] for child in view.children if child.custom_id == "file_select" and child.values), None)
            rank_val = next((child.values[0] for child in view.children if child.custom_id == "rank_select" and child.values), None)
            if not file_val or not rank_val: await interaction.response.send_message("Veuillez sélectionner une colonne ET une rangée.", ephemeral=True); return
            selected_square = chess.square(int(file_val), int(rank_val))
            piece = view.board.piece_at(selected_square)
            if piece is None: await interaction.response.send_message("Il n'y a pas de pièce sur cette case.", ephemeral=True); return
            if piece.color != view.board.turn: await interaction.response.send_message("Ce n'est pas votre pièce.", ephemeral=True); return
            view.create_action_interface(selected_square)
            highlight_color = "#ffcc00aa"; highlight_set = chess.SquareSet([selected_square])
            new_image = await view.generate_board_image(fill=dict.fromkeys(highlight_set, highlight_color))
            await interaction.response.edit_message(content=f"Pièce en **{chess.square_name(selected_square)}** sélectionnée. Choisissez une action.", attachments=[new_image], view=view)
        elif self.custom_id == "show_moves_btn":
            piece = view.board.piece_at(square)
            possible_moves = [move.to_square for move in view.board.pseudo_legal_moves if move.from_square == square]
            if piece.piece_type == chess.PAWN:
                direction = 8 if piece.color == chess.WHITE else -8
                back_square = square - direction
                if 0 <= back_square < 64 and not view.board.piece_at(back_square):
                    if back_square not in possible_moves: possible_moves.append(back_square)
            if not possible_moves: await interaction.response.send_message("Cette pièce ne peut pas bouger.", ephemeral=True); return
            view.create_destination_interface(from_square=square, possible_moves=possible_moves)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"
            fill_colors = dict.fromkeys(chess.SquareSet(possible_moves), moves_color); fill_colors[square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content=f"Déplacement pour la pièce en **{chess.square_name(square)}**. Choisissez une destination.", attachments=[new_image], view=view)
        elif self.custom_id == "royal_sweep_btn":
            neighbor_squares = chess.SquareSet(chess.BB_KING_ATTACKS[square])
            for neighbor_square in neighbor_squares:
                piece_to_capture = view.board.piece_at(neighbor_square)
                if piece_to_capture and piece_to_capture.color != view.board.turn:
                    view.board.remove_piece_at(neighbor_square)
            view.board.push(chess.Move.null())
            if not view.board.king(chess.WHITE) or not view.board.king(chess.BLACK):
                winner = "Noirs" if not view.board.king(chess.WHITE) else "Blancs"
                view.disable_all_items(); final_image = await view.generate_board_image()
                await interaction.response.edit_message(content=f"**Partie terminée ! Le roi a été capturé. Victoire des {winner} !**", attachments=[final_image], view=view)
                return
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"**Balayage Royal !** Pièces adjacentes capturées. C'est au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "double_assault_start_btn":
            possible_moves = [m.to_square for m in view.board.pseudo_legal_moves if m.from_square == square]
            if not possible_moves: await interaction.response.send_message("Ce cavalier ne peut pas bouger.", ephemeral=True); return
            view.create_double_assault_interface(square, possible_moves, step=1)
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"
            fill_colors = dict.fromkeys(chess.SquareSet(possible_moves), moves_color); fill_colors[square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content=f"Double Assaut : Choisissez la première destination pour le cavalier en **{chess.square_name(square)}**.", attachments=[new_image], view=view)
        elif self.custom_id == "teleport_start_btn":
            view.create_teleport_target_interface()
            selection_color = "#ffcc00aa"
            fill_colors = {square: selection_color}
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content="Téléportation : Choisissez une pièce sur l'échiquier qui servira de balise.", attachments=[new_image], view=view)
        elif self.custom_id == "rescue_team_start_btn":
            initial_counts = { chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1 }
            captured_pieces_options = []
            for piece_type, initial_count in initial_counts.items():
                if len(view.board.pieces(piece_type, view.board.turn)) < initial_count:
                    captured_pieces_options.append(discord.SelectOption(label=chess.piece_name(piece_type).capitalize(), value=str(piece_type)))
            if not captured_pieces_options:
                await interaction.response.send_message("Aucune de vos pièces n'a été capturée.", ephemeral=True); return
            view.create_rescue_team_piece_select_interface(captured_pieces_options)
            new_image = await view.generate_board_image(fill={square: "#ffcc00aa"})
            await interaction.response.edit_message(content="Équipe de secours : Une de vos pièces peut revenir au combat !", attachments=[new_image], view=view)
        elif self.custom_id == "mind_control_start_btn":
            target_options = []
            valid_targets = []
            for target_square, piece in view.board.piece_map().items():
                if piece.color != view.board.turn and piece.piece_type != chess.KING:
                    label = f"{chess.piece_name(piece.piece_type).capitalize()} en {chess.square_name(target_square)}"
                    target_options.append(discord.SelectOption(label=label, value=str(target_square)))
                    valid_targets.append(target_square)
            if not target_options:
                await interaction.response.send_message("Il n'y a aucune pièce ennemie (hors Roi) à contrôler.", ephemeral=True); return
            view.create_mind_control_target_interface(target_options)
            selection_color = "#ffcc00aa"; target_color = "#ff4500aa"
            fill_colors = dict.fromkeys(chess.SquareSet(valid_targets), target_color); fill_colors[square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)
            await interaction.response.edit_message(content="Contrôle mental : Choisissez une victime...", attachments=[new_image], view=view)
        elif self.custom_id == "forfeit_btn":
            winner = view.black_player if interaction.user == view.white_player else view.white_player
            view.disable_all_items()
            final_image = await view.generate_board_image()
            content = f"**Partie terminée !** {interaction.user.mention} a abandonné. La victoire revient à {winner.mention} !"
            await interaction.response.edit_message(content=content, attachments=[final_image], view=view)
        elif self.custom_id == "cancel_ability_btn":
            view.board.pop()
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Capacité annulée. C'est toujours au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "cancel_btn":
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Sélection annulée. C'est toujours au tour de {next_player_mention}.", attachments=[new_image], view=view)

class GameRequestView(ui.View):
    message: discord.Message = None
    def __init__(self, initiator: discord.Member, opponent: discord.Member, cog: commands.Cog):
        super().__init__(timeout=60)  # Expire après 60 secondes
        self.initiator = initiator
        self.opponent = opponent
        self.cog = cog

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("Vous n'êtes pas l'adversaire ciblé pour cette partie.", ephemeral=True)
            return
        
        await interaction.response.edit_message(        
                                        content=f"🔥 Défi accepté par {interaction.user.mention} ! La partie commence.",        
                                        view=None  )
        
        # Assignation aléatoire des couleurs
        players = [self.initiator, self.opponent]
        random.shuffle(players)
        white_player, black_player = players[0], players[1]

        board = chess.Board()
        view = GameView(game_board=board, white_player=white_player, black_player=black_player)
        file = await view.generate_board_image()
        
        # Message de départ mis à jour
        await interaction.followup.send(
            f"Nouvelle partie lancée ! {white_player.mention} (Blancs) contre {black_player.mention} (Noirs).\n"
            f"C'est au tour des Blancs ({white_player.mention}).",
            file=file,
            view=view
        )
        self.stop()

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("Vous n'êtes pas l'adversaire ciblé pour cette partie.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"Défi refusé par {interaction.user.mention}.", view=None)
        self.stop()
        
    async def on_timeout(self) -> None:        
        # On désactive tous les boutons        
        for item in self.children:            
            item.disabled = True                
            # On modifie le message original pour indiquer que le défi a expiré        
            # # On passe "view=self" pour que les boutons apparaissent grisés        
        if self.message:            
            await self.message.edit(content="**Ce défi a expiré.**", view=self)

class ChessCog(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    async def send_message(self, member: discord.Member, content: str):
        try:
            await member.send(content)
        except discord.HTTPException:
            pass
    
    @app_commands.command(name="nouvelle_partie", description="Lance une partie d'échecs Royal contre un autre joueur.")
    @app_commands.describe(adversaire="Le joueur que vous souhaitez affronter.")
    async def nouvelle_partie(self, interaction: discord.Interaction, adversaire: discord.Member):
        await interaction.response.defer()
        if adversaire.bot:
            await interaction.followup.send("Vous ne pouvez pas affronter un bot.", ephemeral=True)
            return
        if adversaire == interaction.user:
            await interaction.followup.send("Vous ne pouvez pas vous affronter vous-même !", ephemeral=True)
            return

        view = GameRequestView(initiator=interaction.user, opponent=adversaire, cog=self)
        message = await interaction.followup.send(f"{adversaire.mention}, vous avez été défié par {interaction.user.mention} à une partie d'échecs Royal ! Acceptez-vous ?", view=view)
        view.message = message

async def setup(bot: commands.Bot):
    await bot.add_cog(ChessCog(bot))