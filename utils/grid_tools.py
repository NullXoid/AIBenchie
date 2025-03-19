# grid_tools.py

def grid_cell_to_coordinates(cell, screen_width=1920, screen_height=1080, rows=10, cols=10):
    """
    Convert grid cell label (like D5) into pixel coordinates on screen.
    Assumes a grid from A1 (top-left) to J10 (bottom-right).
    """
    import string

    try:
        row_label = cell[0].upper()
        col_number = int(cell[1:])

        if row_label not in string.ascii_uppercase[:rows] or not (1 <= col_number <= cols):
            raise ValueError("Invalid grid cell label")

        row_index = string.ascii_uppercase.index(row_label)
        col_index = col_number - 1

        cell_width = screen_width // cols
        cell_height = screen_height // rows

        x = (col_index * cell_width) + (cell_width // 2)
        y = (row_index * cell_height) + (cell_height // 2)

        return x, y

    except Exception as e:
        raise ValueError(f"Failed to convert grid cell '{cell}' to coordinates: {e}")
