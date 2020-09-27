#include <unistd.h>
#include <stdlib.h>
#include <signal.h>

/* For the definition of SYS_ioprio_set */
#include <sys/syscall.h>

/* Extracted from the kernel source */
#define IOPRIO_WHO_PROCESS 1
#define IOPRIO_CLASS_IDLE 3
#define _IOPRIO_CLASS_SHIFT 13
#define _IOPRIO_PRIO_MASK ((1 << _IOPRIO_CLASS_SHIFT) - 1)
#define IOPRIO_PRIO_VALUE(cls, dat) (((cls) << _IOPRIO_CLASS_SHIFT) | ((dat) & _IOPRIO_PRIO_MASK))

int main(int argc, char *argv[]) {
    unsigned int timeout;
    char c;

    // Parse the timeout from the command line
    timeout = (argc >= 2 ? atoi(argv[1]) : 120);

    // Make sure that SIGALRM is set to use the default action (i.e. terminate the process)
    signal(SIGALRM, SIG_DFL);

    // Nice ourselves into the background
    nice(40);
    // Also lower the I/O priority
    syscall(SYS_ioprio_set, IOPRIO_WHO_PROCESS, 0, IOPRIO_PRIO_VALUE(IOPRIO_CLASS_IDLE, 0));

    do {
        // Set an alarm
        alarm(timeout);

        // Wait until we read a character from stdin before resetting the alarm
    } while(read(0, &c, 1) == 1);

    return 1;
}

