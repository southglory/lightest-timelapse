"""PyInstaller 진입점."""
import multiprocessing
from reviewer.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller onefile + multiprocessing.Pool 필수 (--multiprocessing-fork 버그 방지)
    main()
