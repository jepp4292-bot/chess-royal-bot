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
        self.royal_pawns = set() # Pour stocker les cases (int) des pions royaux
        self.create_selection_interface()
        
    # Dans la classe GameView (vous pouvez l'ajouter après la méthode __init__)

    def _update_royal_pawn_status(self, move: chess.Move):
        """
        Met à jour le set des pions royaux après un coup.
        Cette méthode gère correctement les déplacements simples et les captures.
        """
        # Étape 1 : On vérifie si une pièce CAPTURÉE était un pion royal.
        # Cette vérification doit se faire AVANT de mettre à jour le pion qui se déplace.
        is_capture = self.board.is_capture(move)
        if is_capture and move.to_square in self.royal_pawns:
            self.royal_pawns.remove(move.to_square)

        # Étape 2 : On vérifie si la pièce qui SE DÉPLACE est un pion royal et on met à jour sa position.
        if move.from_square in self.royal_pawns:
            self.royal_pawns.remove(move.from_square)
            self.royal_pawns.add(move.to_square)

        
    # Dans la classe GameView
    def get_all_possible_moves(self, square: int) -> list[int]:
        """Calcule tous les coups possibles pour une pièce, incluant les règles personnalisées."""
        piece = self.board.piece_at(square)
        if not piece:
            return []

        # On commence avec les coups de base de la bibliothèque (captures, etc.)
        possible_moves = [move.to_square for move in self.board.pseudo_legal_moves if move.from_square == square]
        
        # On ajoute nos règles personnalisées
        if piece.piece_type == chess.PAWN:
            direction = 8 if piece.color == chess.WHITE else -8
            
            # Règle : Reculer d'une case (pour tous les pions)
            back_square = square - direction
            if 0 <= back_square < 64 and not self.board.piece_at(back_square):
                if back_square not in possible_moves: possible_moves.append(back_square)
                
            # --- DÉBUT DE LA CORRECTION POUR LE PION ROYAL ---
            if square in self.royal_pawns:
                # On vérifie les mouvements vers l'avant pas à pas
                one_step = square + direction
                if 0 <= one_step < 64 and self.board.piece_at(one_step) is None:
                    # Le pion royal peut toujours avancer d'une case
                    if one_step not in possible_moves: possible_moves.append(one_step)

                    two_steps = square + (2 * direction)
                    # S'il peut avancer d'une case, peut-il en avancer de deux ?
                    if 0 <= two_steps < 64 and self.board.piece_at(two_steps) is None:
                        if two_steps not in possible_moves: possible_moves.append(two_steps)

                        three_steps = square + (3 * direction)
                        # S'il peut avancer de deux cases, peut-il en avancer de trois ?
                        if 0 <= three_steps < 64 and self.board.piece_at(three_steps) is None:
                            if three_steps not in possible_moves: possible_moves.append(three_steps)

                # Se déplacer sur les diagonales avant (sans capture)
                file, _ = chess.square_file(square), chess.square_rank(square)
                if file > 0: # Diagonale gauche
                    diag_left = square + direction - 1
                    if 0 <= diag_left < 64 and self.board.piece_at(diag_left) is None:
                        if diag_left not in possible_moves: possible_moves.append(diag_left)
                if file < 7: # Diagonale droite
                    diag_right = square + direction + 1
                    if 0 <= diag_right < 64 and self.board.piece_at(diag_right) is None:
                        if diag_right not in possible_moves: possible_moves.append(diag_right)
            # --- FIN DE LA CORRECTION ---
                        
        return possible_moves
    # Dans la classe GameView
    def create_action_and_destination_interface(self, square: int):
        self.clear_items()
        self.selected_square = square
        piece = self.board.piece_at(square)

        # --- PARTIE 1 : Création du menu des destinations ---
        possible_moves = self.get_all_possible_moves(square)

        # On ajoute le menu déroulant seulement s'il y a des coups possibles
        if possible_moves:
            move_options = [discord.SelectOption(label=chess.square_name(sq), value=str(sq)) for sq in possible_moves]
            self.add_item(Dropdown(placeholder="Choisissez une destination...", options=move_options, custom_id="destination_select"))

        # --- PARTIE 2 : Ajout des boutons de capacité ---
        if piece.piece_type == chess.KING: self.add_item(Button(label="Promotion Royale 🎖️", style=discord.ButtonStyle.success, custom_id="royal_promotion_start_btn"))
        elif piece.piece_type == chess.KNIGHT: self.add_item(Button(label="Double Assaut ⚔️", style=discord.ButtonStyle.success, custom_id="double_assault_start_btn"))
        elif piece.piece_type == chess.BISHOP: self.add_item(Button(label="Téléportation ✨", style=discord.ButtonStyle.success, custom_id="teleport_start_btn"))
        elif piece.piece_type == chess.ROOK: self.add_item(Button(label="Équipe de secours 🛡️", style=discord.ButtonStyle.success, custom_id="rescue_team_start_btn"))
        elif piece.piece_type == chess.QUEEN: self.add_item(Button(label="Contrôle mental 🧠", style=discord.ButtonStyle.success, custom_id="mind_control_start_btn"))
        
        # --- PARTIE 3 : Ajout des boutons standards ---
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.danger, row=3, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))
        
        return possible_moves

            # Dans la classe GameView
    def create_selection_interface(self):
            self.clear_items()
            self.selected_square = None
            self.ability_piece_type = None
            self.mind_control_target = None

            # --- NOUVELLE LOGIQUE DE SÉLECTION ---
            piece_options = []
            current_turn_color = self.board.turn
            # On parcourt toutes les pièces sur l'échiquier
            for square, piece in self.board.piece_map().items():
                # Si la pièce appartient au joueur dont c'est le tour
                if piece.color == current_turn_color:
                    # On vérifie si la pièce a au moins un coup pseudo-légal
                    # (pour ne pas proposer des pièces complètement bloquées)
                
                    piece_name_fr = {
                        chess.PAWN: "Pion", chess.KNIGHT: "Cavalier", chess.BISHOP: "Fou",
                        chess.ROOK: "Tour", chess.QUEEN: "Dame", chess.KING: "Roi"
                    }.get(piece.piece_type, "Pièce")
                        
                    label = f"{piece_name_fr} en {chess.square_name(square)}"
                    piece_options.append(discord.SelectOption(label=label, value=str(square)))    

            if piece_options:
                # On crée le nouveau menu déroulant avec un custom_id clair
                self.add_item(Dropdown(placeholder="Choisissez une pièce à jouer...", options=piece_options, custom_id="piece_select"))
            
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
        fill_colors = kwargs.pop('fill', {}) # Récupère les couleurs existantes
    
    # Ajoute la couleur dorée pour les pions royaux
        for royal_pawn_square in self.royal_pawns:
        # On ne surcharge pas une couleur de sélection ou de mouvement
            if royal_pawn_square not in fill_colors:
                fill_colors[royal_pawn_square] = "#ffd700aa" # Or avec transparence
            
        svg_board = chess.svg.board(board=self.board, fill=fill_colors, **kwargs)
        png_board = cairosvg.svg2png(bytestring=svg_board.encode('utf-8'))
        return discord.File(fp=BytesIO(png_board), filename="echiquier.png")
    def disable_all_items(self):
        for item in self.children: item.disabled = True; self.stop()
    def create_royal_promotion_target_interface(self, pawn_options: list[discord.SelectOption]):
        self.clear_items()
        self.add_item(Dropdown(placeholder="Quel pion anoblir ?", options=pawn_options, custom_id="royal_promotion_target_select"))
        self.add_item(Button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_btn"))
        self.add_item(Button(label="Abandonner", style=discord.ButtonStyle.danger, row=4, custom_id="forfeit_btn"))


        

# --- COMPOSANTS D'INTERFACE ---
class Dropdown(ui.Select):
    async def callback(self, interaction: discord.Interaction):
        view: GameView = self.view
        current_player = view.white_player if view.board.turn == chess.WHITE else view.black_player
        if interaction.user != current_player:
            await interaction.response.send_message("Ce n'est pas votre tour de jouer !", ephemeral=True)
            return
        from_square = view.selected_square
        
        
        if self.custom_id == "piece_select":
            await interaction.response.defer()
            selected_square = int(self.values[0])
            
            # --- NOUVELLE LOGIQUE SIMPLIFIÉE ---
            # On appelle notre nouvelle fonction unifiée
            possible_moves = view.create_action_and_destination_interface(selected_square)
            
            # On prépare l'image pour la réponse

            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"
            fill_colors = dict.fromkeys(chess.SquareSet(possible_moves), moves_color)
            fill_colors[selected_square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)

            await interaction.edit_original_response(content=f"Pièce en **{chess.square_name(selected_square)}** sélectionnée. Choisissez un coup ou une capacité.", attachments=[new_image], view=view)
        elif self.custom_id == "destination_select":
            to_square = int(self.values[0]); move = chess.Move(from_square, to_square)
                        # On met à jour la position du pion royal s'il a bougé
                        
            view._update_royal_pawn_status(move)
            view.board.push(move)
    
            if not view.board.king(chess.WHITE) or not view.board.king(chess.BLACK):
                winner = "Noirs" if not view.board.king(chess.WHITE) else "Blancs"
                view.disable_all_items(); final_image = await view.generate_board_image()
                await interaction.response.edit_message(content=f"**Partie terminée ! Le roi a été capturé. Victoire des {winner} !**", attachments=[final_image], view=view)
                return
            view.create_selection_interface(); new_image = await view.generate_board_image()
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Coup joué ! C'est au tour de {next_player_mention}.", attachments=[new_image], view=view)
        elif self.custom_id == "royal_promotion_target_select":
            pawn_to_promote_square = int(self.values[0])
        
            # On ajoute le pion à notre liste de suivi
            view.royal_pawns.add(pawn_to_promote_square)
        
            # On passe le tour
            view.board.push(chess.Move.null())
        
            view.create_selection_interface()
            # On surligne le nouveau pion royal en or
            new_image = await view.generate_board_image(fill={pawn_to_promote_square: "#ffd700aa"})
            next_player_mention = view.white_player.mention if view.board.turn else view.black_player.mention
            await interaction.response.edit_message(content=f"Le pion en **{chess.square_name(pawn_to_promote_square)}** est devenu un **Pion Royal** ! Au tour de {next_player_mention}.", attachments=[new_image], view=view)

        elif self.custom_id == "double_assault_move1_select":
            to_square = int(self.values[0]); move = chess.Move(from_square, to_square)
                
                        
            view._update_royal_pawn_status(move)
        

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
                        # On met à jour la position du pion royal s'il a bougé
                        
            view._update_royal_pawn_status(move)
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
        # Dans la classe Dropdown, méthode callback
        elif self.custom_id == "mind_control_target_select":
            # On diffère la réponse pour éviter les timeouts
            await interaction.response.defer()
            
            target_square = int(self.values[0])
            view.mind_control_target = target_square

            # --- DÉBUT DE LA CORRECTION SÉCURISÉE ---

            # Étape 1 : Calculer les coups possibles de la pièce ennemie
            # On inverse le tour JUSTE pour le calcul, puis on le restaure immédiatement.
            view.board.turn = not view.board.turn
            destination_squares = view.get_all_possible_moves(target_square)
            view.board.turn = not view.board.turn # Restauration immédiate de l'état correct

            # Si aucun coup n'est possible, on peut s'arrêter ici en toute sécurité.
            if not destination_squares:
                # On utilise edit_original_response car on a "defer" au début
                await interaction.edit_original_response(content="Cette pièce ennemie ne peut effectuer aucun coup.", view=view)
                return

            # Étape 2 : Obtenir la notation des coups (ex: "Nf3")
            # On a besoin de ré-inverser le tour pour que board.san() fonctionne correctement.
            possible_moves_obj = [chess.Move(target_square, dest) for dest in destination_squares]
            view.board.turn = not view.board.turn
            destination_options = [discord.SelectOption(label=view.board.san(m), value=m.uci()) for m in possible_moves_obj]
            view.board.turn = not view.board.turn # Restauration immédiate de l'état correct

            # --- FIN DE LA CORRECTION SÉCURISÉE ---

            # À ce point, view.board.turn est GARANTI d'être correct.
            # Le bouton "Annuler" fonctionnera donc parfaitement.
            view.create_mind_control_destination_interface(destination_options)
            
            # On prépare l'image et on envoie la réponse finale
            selection_color = "#ffcc00aa"; moves_color = "#228B22aa"; target_color = "#ff4500aa"
            fill_colors = dict.fromkeys(destination_squares, moves_color)
            fill_colors[from_square] = selection_color; fill_colors[target_square] = target_color
            new_image = await view.generate_board_image(fill=fill_colors)
            
            await interaction.edit_original_response(
                content="Pièce ennemie sous contrôle. Quel coup désastreux allez-vous la forcer à jouer ?", 
                attachments=[new_image], 
                view=view
            )
        elif self.custom_id == "mind_control_destination_select":
            move_uci = self.values[0]
            forced_move = chess.Move.from_uci(move_uci)
                        # On met à jour la position du pion royal s'il a bougé
            view._update_royal_pawn_status(forced_move)
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
        if self.custom_id == "royal_promotion_start_btn":
            allied_pawns = []
            # On cherche tous les pions de la couleur du joueur
            for pawn_square, pawn_piece in view.board.piece_map().items():
                if pawn_piece.piece_type == chess.PAWN and pawn_piece.color == view.board.turn:
                    # On s'assure qu'il n'est pas déjà un pion royal
                    if pawn_square not in view.royal_pawns:
                        allied_pawns.append(discord.SelectOption(
                            label=f"Pion en {chess.square_name(pawn_square)}",
                            value=str(pawn_square)
                        ))
            
            if not allied_pawns:
                await interaction.response.send_message("Vous n'avez aucun pion non-royal à promouvoir.", ephemeral=True)
                return

            view.create_royal_promotion_target_interface(allied_pawns)
            
            selection_color = "#ffcc00aa"; target_color = "#ffd700aa" # Gold for pawns
            fill_colors = {sq.value: target_color for sq in allied_pawns}
            fill_colors[square] = selection_color
            new_image = await view.generate_board_image(fill=fill_colors)

            await interaction.response.edit_message(content="**Promotion Royale** : Choisissez un pion à anoblir.", attachments=[new_image], view=view)

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
    
    # Dans la classe ChessCog
    @app_commands.command(name="nouvelle_partie", description="Lance une partie d'échecs Royal contre un autre joueur.")
    @app_commands.describe(adversaire="Le joueur que vous souhaitez affronter.")
    async def nouvelle_partie(self, interaction: discord.Interaction, adversaire: discord.Member):
        # On ne fait plus de defer() ici. On répond directement.
        if adversaire.bot:
            # On envoie une réponse initiale et on s'arrête.
            await interaction.response.send_message("Vous ne pouvez pas affronter un bot.", ephemeral=True)
            return
        if adversaire == interaction.user:
            # Idem ici.
            await interaction.response.send_message("Vous ne pouvez pas vous affronter vous-même !", ephemeral=True)
            return

        # On crée la vue comme avant.
        view = GameRequestView(initiator=interaction.user, opponent=adversaire, cog=self)
        
        # On envoie le message de défi comme réponse initiale.
        await interaction.response.send_message(
            f"{adversaire.mention}, vous avez été défié par {interaction.user.mention} à une partie d'échecs Royal ! Acceptez-vous ?", 
            view=view
        )
        
        # TRÈS IMPORTANT : On récupère l'objet Message qu'on vient d'envoyer
        # pour que la vue puisse le modifier en cas de timeout.
        message = await interaction.original_response()
        view.message = message

async def setup(bot: commands.Bot):
    await bot.add_cog(ChessCog(bot))