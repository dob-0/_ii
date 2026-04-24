import time, random, sys, os
CHARS = ["█", "▓", "▒", "░", "▚", "◈", "MOCT", "7"]
COLORS = ["\033[91m", "\033[92m", "\033[97m", "\033[0m"]
def glitch():
    try:
        os.system('clear')
        while True:
            w = os.get_terminal_size().columns
            line = "".join(random.choice(COLORS) + random.choice(CHARS) + "\033[0m" for _ in range(w))
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            time.sleep(random.uniform(0.01, 0.05))
    except KeyboardInterrupt: sys.exit()
if __name__ == "__main__": glitch()
