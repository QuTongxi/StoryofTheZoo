"""One program, two adapters. CLI never imports the GUI entry point."""
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--cli' in args and '--gui' in args:
        print('不能同时使用 --cli 和 --gui', file=sys.stderr)
        return 2
    if '--cli' in args:
        args.remove('--cli')
        from cli.app import main as run
    else:
        if '--gui' in args:
            args.remove('--gui')
        from gui.app import main as run
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
