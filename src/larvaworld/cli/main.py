from ..lib import reg, aux
from .argparser import SimModeParser


def main():
    P = SimModeParser()
    P.parse_args()
    P.configure(show_args=False)
    P.launch()


if __name__ == '__main__':
    main()
