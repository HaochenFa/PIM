"""Composition root: python pim.py"""

from controller import App
from model import PIM
from view import Terminal


def main():
    """PIM() → App(pim) → Terminal(app) → run()."""
    pim = PIM()
    app = App(pim)
    Terminal(app).run()


if __name__ == "__main__":
    main()
