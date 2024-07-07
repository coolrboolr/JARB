
# subtractor.py
def subtract_numbers(a, b):
    """
    Subtract two numbers.

    Parameters:
    a (int or float): First number.
    b (int or float): Second number.

    Returns:
    float: Result of subtraction a - b.

    Raises:
    TypeError: If inputs are not int or float.
    ValueError: If inputs cannot be converted to float.
    """
    # Step 3: Input Validation
    try:
        a = float(a)
        b = float(b)
    except ValueError:
        raise ValueError("Both inputs must be numeric values.")
    
    # Step 4: Subtraction Process and Return Result
    result = a - b
    return result
