import os, sys, time
def blackout():
    try:
        sys.stdout.write("\033[?25l")
        os.system('cls' if os.name == 'nt' else 'clear')
        sys.stdout.write("\033[40m")
        sys.stdout.flush()
        while True: time.sleep(1)
    except KeyboardInterrupt:
        sys.stdout.write("\033[?25h\033[0m")
        os.system('cls' if os.name == 'nt' else 'clear')
if __name__ == "__main__": blackout()
