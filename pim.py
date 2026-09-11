"""Composition root: python pim.py"""

from controller import App
from model import PIM
from view import Terminal


def main():
    pim = PIM()
    app = App(pim)
    try:
        Terminal(app).run()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
