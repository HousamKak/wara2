"""
Image generation utilities for the Wara2 Card Games Bot.
"""

import os
import logging
from io import BytesIO
from typing import List, Optional, Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

from constants import POSITIONS, CARD_STYLES, DEFAULT_CARD_STYLE
from utils.cards import get_card_emoji, card_to_filename

# Type alias
CardType = Tuple[str, str]  # (rank, suit)

# Configure logger
logger = logging.getLogger(__name__)


def create_trick_board_text(trick: List[Optional[CardType]], player_names: Dict[str, str]) -> str:
    """Create a text representation of the trick board.
    
    Args:
        trick: The cards in the current trick (in order of POSITIONS)
        player_names: Dictionary mapping positions to player names
        
    Returns:
        A cross-style board as text
    """
    # Use a fixed order for positions in the trick display
    trick_order = ["top", "left", "bottom", "right"]
    
    # Extract cards for each position (may be None if not played yet)
    top_card = trick[0] if len(trick) > 0 else None
    left_card = trick[1] if len(trick) > 1 else None
    bottom_card = trick[2] if len(trick) > 2 else None
    right_card = trick[3] if len(trick) > 3 else None
    
    # Format the card display
    top_display = get_card_emoji(top_card)
    left_display = get_card_emoji(left_card)
    right_display = get_card_emoji(right_card)
    bottom_display = get_card_emoji(bottom_card)
    
    # Get player names
    top_name = player_names.get("top", "Top")
    left_name = player_names.get("left", "Left")
    right_name = player_names.get("right", "Right")
    bottom_name = player_names.get("bottom", "Bottom")
    
    # Create the board
    board = [
        f"         {top_name} (Top)",
        f"            {top_display}",
        f"",
        f"{left_name} {left_display}           {right_display} {right_name}",
        f"(Left)                                     (Right)",
        f"",
        f"            {bottom_display}",
        f"         {bottom_name} (Bottom)"
    ]
    
    return "\n".join(board)


def create_trick_board_image(
    trick: List[Optional[CardType]], 
    player_names: Dict[str, str],
    card_style: str = DEFAULT_CARD_STYLE,
    game_name: str = "Li5a"
) -> BytesIO:
    """Create an image representation of the trick board.
    
    Args:
        trick: The cards in the current trick (in order of POSITIONS)
        player_names: Dictionary mapping positions to player names
        card_style: Card style to use ("standard", "small", "minimal")
        game_name: Name of the game for the title
        
    Returns:
        BytesIO object containing the image
    """
    # Get card dimensions from style
    style_dimensions = CARD_STYLES.get(card_style, CARD_STYLES[DEFAULT_CARD_STYLE])
    CARD_WIDTH = style_dimensions["width"]
    CARD_HEIGHT = style_dimensions["height"]
    
    # Image dimensions - adjust based on card size
    width, height = 600, 600
    
    # Create a blank image with white background
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    
    # Try to load a font or use default
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        name_font = ImageFont.truetype("arial.ttf", 18)
        title_font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        title_font = name_font
    
    # Card positions on the board
    card_positions = {
        "top": (width // 2 - CARD_WIDTH // 2, 100),
        "left": (100, height // 2 - CARD_HEIGHT // 2),
        "right": (width - 100 - CARD_WIDTH, height // 2 - CARD_HEIGHT // 2),
        "bottom": (width // 2 - CARD_WIDTH // 2, height - 100 - CARD_HEIGHT)
    }
    
    # Name positions near the cards
    name_positions = {
        "top": (width // 2, 70),
        "left": (50, height // 2),
        "right": (width - 50, height // 2),
        "bottom": (width // 2, height - 70)
    }
    
    # Extract cards for each position using a fixed order for consistency
    position_cards = {
        "top": trick[0] if len(trick) > 0 else None,
        "left": trick[1] if len(trick) > 1 else None,
        "bottom": trick[2] if len(trick) > 2 else None,
        "right": trick[3] if len(trick) > 3 else None
    }
    
    # Draw each card and name
    for position in POSITIONS:
        card = position_cards[position]
        
        # Draw card (placeholder if not played yet)
        x, y = card_positions[position]
        if card:
            # Try to load card image or draw a placeholder
            try:
                card_file = f"card_images/{card_to_filename(card)}"
                if os.path.exists(card_file):
                    card_img = Image.open(card_file)
                    card_img = card_img.resize((CARD_WIDTH, CARD_HEIGHT))
                    image.paste(card_img, (x, y))
                else:
                    # Draw placeholder with text if image not found
                    draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="lightgray")
                    card_text = get_card_emoji(card)
                    text_x = x + CARD_WIDTH // 4
                    text_y = y + CARD_HEIGHT // 3
                    draw.text((text_x, text_y), card_text, fill="black", font=font)
                    logger.warning(f"Card image not found: {card_file}")
            except Exception as e:
                logger.error(f"Error loading card image: {e}")
                # Draw placeholder with text
                draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="lightgray")
                card_text = get_card_emoji(card)
                draw.text((x + CARD_WIDTH // 4, y + CARD_HEIGHT // 3), card_text, fill="black", font=font)
        else:
            # Draw empty placeholder
            draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="white")
        
        # Draw player name
        name = player_names.get(position, position.capitalize())
        x, y = name_positions[position]
        
        # Add indication if player is AI
        if name.endswith(" (AI)"):
            name_color = "blue"
        else:
            name_color = "black"
        
        # Adjust text position based on board position
        if position == "top":
            draw.text((x - 50, y), f"{name} (Top)", fill=name_color, font=name_font)
        elif position == "bottom":
            draw.text((x - 50, y), f"{name} (Bottom)", fill=name_color, font=name_font)
        elif position == "left":
            draw.text((x - 40, y), f"{name} (Left)", fill=name_color, font=name_font)
        elif position == "right":
            draw.text((x - 40, y), f"{name} (Right)", fill=name_color, font=name_font)
    
    # Draw a title at the top of the image
    title = f"{game_name} Card Game - Current Trick"
    title_width = draw.textlength(title, font=title_font)
    draw.text((width // 2 - title_width // 2, 20), title, fill="black", font=title_font)
    
    # Draw team indicators
    draw.text((width // 2 - 100, 45), "Team A: Top & Bottom", fill="red", font=font)
    draw.text((width // 2 + 10, 45), "Team B: Left & Right", fill="blue", font=font)
    
    # Save image to bytes
    img_bytes = BytesIO()
    image.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    
    return img_bytes

def create_hand_image(
    hand: List[CardType],
    selected_cards: Optional[List[CardType]] = None,
    card_style: str = DEFAULT_CARD_STYLE
) -> BytesIO:
    """Create an image of a player's hand."""
    logger.info(f"Creating hand image with {len(hand)} cards, style: {card_style}")
    logger.debug(f"Hand content: {[get_card_emoji(card) for card in hand]}")
    
    if selected_cards is None:
        selected_cards = []
    
    try:
        # Get card dimensions from style
        style_dimensions = CARD_STYLES.get(card_style, CARD_STYLES[DEFAULT_CARD_STYLE])
        CARD_WIDTH = style_dimensions["width"]
        CARD_HEIGHT = style_dimensions["height"]
        
        # Sort the hand
        sorted_hand = sorted(hand, key=lambda c: (c[1], next((i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]) if r == c[0]), -1)))
        
        # Calculate image dimensions
        cards_per_row = 7
        num_rows = (len(sorted_hand) + cards_per_row - 1) // cards_per_row
        
        # Add 10px spacing between cards
        spacing = 10
        
        # Image width with spacing
        image_width = min(len(sorted_hand), cards_per_row) * (CARD_WIDTH + spacing) + spacing
        image_height = num_rows * (CARD_HEIGHT + spacing) + spacing + 30  # Extra for title
        
        logger.debug(f"Creating image with dimensions: {image_width}x{image_height}")
        
        # Create a blank image with white background
        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)
        
        # Try to load a font or use default
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            title_font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            logger.warning("Could not load Arial font, using default font")
            font = ImageFont.load_default()
            title_font = font
        
        # Draw title
        title = "Your Cards"
        draw.text((spacing, spacing), title, fill="black", font=title_font)
        
        # Draw cards
        card_load_errors = 0
        for i, card in enumerate(sorted_hand):
            row = i // cards_per_row
            col = i % cards_per_row
            
            # Calculate position
            x = col * (CARD_WIDTH + spacing) + spacing
            y = row * (CARD_HEIGHT + spacing) + spacing + 30  # Account for title
            
            # Draw card
            try:
                card_file = f"card_images/{card_to_filename(card)}"
                logger.debug(f"Loading card image: {card_file}")
                
                if os.path.exists(card_file):
                    card_img = Image.open(card_file)
                    card_img = card_img.resize((CARD_WIDTH, CARD_HEIGHT))
                    
                    # If card is selected, add highlight
                    if card in selected_cards:
                        # Create highlight effect
                        highlight = Image.new("RGBA", (CARD_WIDTH + 6, CARD_HEIGHT + 6), (0, 255, 0, 128))
                        image.paste(highlight, (x - 3, y - 3), highlight)
                    
                    image.paste(card_img, (x, y))
                    
                    # Draw card index number
                    draw.text((x + 5, y + 5), str(i+1), fill="black", font=font)
                else:
                    logger.warning(f"Card image not found: {card_file}")
                    # Draw placeholder
                    draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="white")
                    card_text = get_card_emoji(card)
                    draw.text((x + CARD_WIDTH // 4, y + CARD_HEIGHT // 3), card_text, fill="black", font=font)
                    draw.text((x + 5, y + 5), str(i+1), fill="black", font=font)
                    card_load_errors += 1
            except Exception as e:
                logger.error(f"Error drawing card image for {get_card_emoji(card)}: {e}")
                # Draw placeholder
                draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="white")
                card_text = get_card_emoji(card)
                draw.text((x + CARD_WIDTH // 4, y + CARD_HEIGHT // 3), card_text, fill="black", font=font)
                draw.text((x + 5, y + 5), str(i+1), fill="black", font=font)
                card_load_errors += 1
        
        if card_load_errors > 0:
            logger.warning(f"Failed to load {card_load_errors} card images")
        
        # Save image to bytes
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        # Check if image was created successfully
        buffer_size = img_bytes.getbuffer().nbytes
        logger.info(f"Hand image created successfully: {buffer_size} bytes")
        
        if buffer_size == 0:
            logger.error("Created image buffer is empty!")
            # Create a simple fallback image
            fallback = Image.new("RGB", (400, 200), "white")
            draw = ImageDraw.Draw(fallback)
            draw.text((20, 20), "Hand visualization unavailable - using fallback", fill="black", font=font)
            img_bytes = BytesIO()
            fallback.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            logger.info(f"Created fallback image: {img_bytes.getbuffer().nbytes} bytes")
        
        return img_bytes
    except Exception as e:
        logger.error(f"Unhandled exception in create_hand_image: {e}", exc_info=True)
        # Return a minimal valid image as fallback
        try:
            fallback = Image.new("RGB", (400, 200), "white")
            draw = ImageDraw.Draw(fallback)
            draw.text((20, 20), "Error creating hand image - please check logs", fill="black", font=ImageFont.load_default())
            
            img_bytes = BytesIO()
            fallback.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            logger.info("Created emergency fallback image due to error")
            return img_bytes
        except Exception as emergency_e:
            logger.critical(f"Even fallback image creation failed: {emergency_e}")
            raise
        
# Add a utility function to create a fresh image buffer
def create_fresh_image_buffer(image_generator_func, *args):
    """Safely create a BytesIO buffer with image data.
    
    Args:
        image_generator_func: Function that generates the image
        *args: Arguments to pass to the image generator function
        
    Returns:
        A fresh BytesIO buffer containing the image or None if generation fails
    """
    try:
        # Get the image bytes
        buffer = image_generator_func(*args)
        
        # Ensure the buffer is non-empty and positioned at the start
        if buffer and buffer.getbuffer().nbytes > 0:
            buffer.seek(0)
            return buffer
        else:
            logger.error(f"Generated empty image buffer")
            return None
    except Exception as e:
        logger.error(f"Failed to generate image: {e}")
        return None