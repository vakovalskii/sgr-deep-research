"""ASCII art logos for SGR CLI."""

# Short version (medium width terminals)
SHORT_ASCII_LOGO = """
 ███████  ██████  ██████  
██       ██    ██ ██   ██ 
███████  ██    ██ ██████   
     ██  ██    ██ ██   ██ 
███████   ██████  ██   ██  
"""

# Long version (wide terminals) - more detailed
LONG_ASCII_LOGO = """
 ███████  ██████  ██████  
██       ██    ██ ██   ██ 
███████  ██    ██ ██████   
     ██  ██    ██ ██   ██ 
███████   ██████  ██   ██  
"""

# Tiny version (narrow terminals)
TINY_ASCII_LOGO = """
███  ███  ███
███  ███  ███
███  ███  ███
███  ███  ███
███  ███  ███
"""

# Full version with description
FULL_ASCII_LOGO = """
 ███████  ██████  ██████  
██       ██    ██ ██   ██ 
███████  ██    ██ ██████   
     ██  ██    ██ ██   ██ 
███████   ██████  ██   ██  

Schema-Guided Reasoning Agent
"""


def get_ascii_logo(terminal_width: int = 80) -> str:
    """Get appropriate ASCII logo based on terminal width.
    
    Args:
        terminal_width: Width of the terminal in characters
        
    Returns:
        ASCII logo string
    """
    if terminal_width >= 60:
        return LONG_ASCII_LOGO.strip()
    elif terminal_width >= 40:
        return SHORT_ASCII_LOGO.strip()
    else:
        return TINY_ASCII_LOGO.strip()


def get_full_logo(terminal_width: int = 80) -> str:
    """Get full ASCII logo with description.
    
    Args:
        terminal_width: Width of the terminal in characters (unused, kept for compatibility)
    
    Returns:
        Full ASCII logo string
    """
    return FULL_ASCII_LOGO.strip()
