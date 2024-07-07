
import unittest

def subtract_numbers(a, b):
    """
    Subtracts the second number (b) from the first number (a) and returns the result.

    Parameters:
    a (float or int or str): The first number (minuend).
    b (float or int or str): The second number (subtrahend).

    Returns:
    float or int: The difference between a and b.

    Raises:
    TypeError: If either a or b is not a number and cannot be converted to a number.

    Example Usage:
    >>> subtract_numbers(10, 5)
    5

    >>> subtract_numbers(10.5, 1.2)
    9.3

    >>> subtract_numbers('10', '5.5')
    4.5

    >>> subtract_numbers(0, 0)
    0

    >>> subtract_numbers(-10, -5)
    -5

    >>> subtract_numbers(1e18, 1e17)
    9e+17

    >>> subtract_numbers('abc', 5)
    Traceback (most recent call last):
    ...
    TypeError: Input a could not be converted to a number.
    """
    # Inner function to convert input to a number (either int or float)
    def to_number(x):
        if isinstance(x, (int, float)):
            return x
        if isinstance(x, str):
            try:
                return float(x) if '.' in x else int(x)
            except ValueError:
                raise TypeError(f"Input {x} could not be converted to a number.")
        raise TypeError(f"Input {x} is not a valid number type.")

    # Convert inputs
    a = to_number(a)
    b = to_number(b)

    # Perform subtraction
    result = a - b
    return result

class TestSubtractNumbers(unittest.TestCase):
    # Valid number subtraction case using integers
    def test_integers(self):
        self.assertEqual(subtract_numbers(10, 5), 5)
        
    # Valid number subtraction case using floats and strings
    def test_floats_and_strings(self):
        self.assertAlmostEqual(subtract_numbers(10.5, '1.2'), 9.3)
        
    # Invalid inputs case
    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            subtract_numbers('abc', 5)

if __name__ == "__main__":
    unittest.main()
