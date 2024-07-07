
def add_two_numbers(num1, num2):
    """
    Adds two numbers together.

    Parameters:
    num1 (int, float, str): The first number to add. Can be an integer, float, or numeric string.
    num2 (int, float, str): The second number to add. Can be an integer, float, or numeric string.

    Returns:
    float: The sum of num1 and num2.

    Raises:
    TypeError: If either num1 or num2 is not a number or a numeric string.

    Examples:
    >>> add_two_numbers(3, 5)
    8
    >>> add_two_numbers(3.2, 5)
    8.2
    >>> add_two_numbers("4", "5")
    9.0
    >>> add_two_numbers("4.5", 5)
    9.5
    """
    
    # Convert numeric strings to floats if possible
    if isinstance(num1, str):
        try:
            num1 = float(num1)
        except ValueError:
            raise TypeError(f"Invalid input: '{num1}' is not a numeric string")
    
    if isinstance(num2, str):
        try:
            num2 = float(num2)
        except ValueError:
            raise TypeError(f"Invalid input: '{num2}' is not a numeric string")
    
    # Check if inputs are numbers (int or float)
    if not isinstance(num1, (int, float)):
        raise TypeError(f"Invalid input: '{num1}' is not a number")
    
    if not isinstance(num2, (int, float)):
        raise TypeError(f"Invalid input: '{num2}' is not a number")
    
    # Perform addition and return result
    return num1 + num2


# Unit tests
import unittest

class TestAddTwoNumbers(unittest.TestCase):
    def test_integers(self):
        self.assertEqual(add_two_numbers(1, 2), 3)
    
    def test_floats(self):
        self.assertAlmostEqual(add_two_numbers(1.5, 2.3), 3.8)
    
    def test_mixed_types(self):
        self.assertAlmostEqual(add_two_numbers(1, 2.5), 3.5)
    
    def test_zero(self):
        self.assertEqual(add_two_numbers(0, 0), 0)
        self.assertEqual(add_two_numbers(0, 5), 5)
        self.assertEqual(add_two_numbers(5, 0), 5)
    
    def test_large_numbers(self):
        self.assertEqual(add_two_numbers(1e10, 1e10), 2e10)
    
    def test_negative_numbers(self):
        self.assertEqual(add_two_numbers(-1, -2), -3)
        self.assertEqual(add_two_numbers(-1.5, -2.5), -4)
    
    def test_numeric_strings(self):
        self.assertAlmostEqual(add_two_numbers("4", "5"), 9.0)
        self.assertAlmostEqual(add_two_numbers("4.5", "5.5"), 10.0)
        self.assertAlmostEqual(add_two_numbers("4.5", 5.5), 10.0)
    
    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            add_two_numbers("four", 5)
        with self.assertRaises(TypeError):
            add_two_numbers(4, "five")
        with self.assertRaises(TypeError):
            add_two_numbers(None, 5)
        with self.assertRaises(TypeError):
            add_two_numbers(4, None)

if __name__ == '__main__':
    unittest.main()
