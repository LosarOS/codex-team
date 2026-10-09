"""Source and frozen desktop entrypoint; CLI remains separate."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from codex_team.desktop import main
    main()
