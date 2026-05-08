#define _POSIX_C_SOURCE 199309L

#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static volatile sig_atomic_t running = 1;

static void stop(int sig) {
    (void)sig;
    running = 0;
}

static double env_double(const char *name, double fallback) {
    const char *raw = getenv(name);
    char *end = NULL;
    double value;

    if (raw == NULL || *raw == '\0') {
        return fallback;
    }

    value = strtod(raw, &end);
    if (end == raw || value <= 0.0) {
        return fallback;
    }

    return value;
}

static void terminal_size(int *rows, int *cols) {
    struct winsize ws;

    *rows = 40;
    *cols = 120;

    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0) {
        if (ws.ws_row >= 4) {
            *rows = ws.ws_row;
        }
        if (ws.ws_col >= 20) {
            *cols = ws.ws_col;
        }
    }
}

int main(void) {
    const char glyphs[] = " .:-=+*#%@";
    const int colors[] = {16, 17, 18, 19, 20, 21, 27, 33, 39, 45, 51, 87, 159, 231};
    const int color_count = (int)(sizeof(colors) / sizeof(colors[0]));
    double fps = env_double("_II_FPS", 30.0);
    long frame = 0;

    signal(SIGINT, stop);
    signal(SIGTERM, stop);

    printf("\033[2J\033[?25l");
    fflush(stdout);

    while (running) {
        int rows;
        int cols;
        int height;
        int y;
        double t = (double)frame / fps;
        struct timespec delay;

        terminal_size(&rows, &cols);
        height = rows - 1;

        for (y = 1; y <= height; y++) {
            int x;
            int last_color = -1;
            printf("\033[%d;1H", y);

            for (x = 1; x <= cols; x++) {
                double cx = ((double)x - (double)cols * 0.5) / ((double)cols * 0.5);
                double cy = ((double)y - (double)height * 0.5) / ((double)height * 0.5);
                double r = sqrt(cx * cx + cy * cy);
                double a = atan2(cy, cx);
                double v = 0.0;
                int gi;
                int ci;
                int color;

                v += sin(12.0 * r - t * 5.0);
                v += sin(4.0 * a + t * 2.3);
                v += sin(((double)x * 0.09) + ((double)y * 0.04) + t * 3.1);
                v = (v + 3.0) / 6.0;
                if (v < 0.0) {
                    v = 0.0;
                } else if (v > 1.0) {
                    v = 1.0;
                }

                gi = (int)(v * 9.0);
                if (gi < 0) {
                    gi = 0;
                } else if (gi > 9) {
                    gi = 9;
                }

                ci = (int)(v * (double)(color_count - 1));
                color = colors[ci];
                if (color != last_color) {
                    printf("\033[38;5;%dm", color);
                    last_color = color;
                }

                putchar(glyphs[gi]);
            }
        }

        printf("\033[0m\033[%d;1H\033[38;5;250m_ii c-ansi | frame %06ld | Ctrl-C stop\033[0m", rows, frame);
        fflush(stdout);

        delay.tv_sec = 0;
        delay.tv_nsec = (long)(1000000000.0 / fps);
        nanosleep(&delay, NULL);
        frame++;
    }

    printf("\033[0m\033[?25h\n");
    fflush(stdout);
    return 0;
}
