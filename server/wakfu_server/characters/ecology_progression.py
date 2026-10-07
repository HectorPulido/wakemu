"""Ecology domain units are signed basis points; native UI uses a curve."""
import math

LIMIT = 9900


def basis_points(number):
    if type(number) is not int or not -LIMIT <= number <= LIMIT:
        raise ValueError("Invalid ecology basis points")
    return number


def native_score(number):
    number = basis_points(number)
    if number == 0:
        return 0
    magnitude = round(-500 * math.log2(1 - abs(number) / 10000))
    return magnitude if number > 0 else -magnitude
