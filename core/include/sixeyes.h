/* The plain C interface to the SixEyes link, for any language that can call C.
 * It moves whole frames (type, seq, payload). What the messages mean is in protocol/generated/sixeyes_protocol.h. */
#ifndef SIXEYES_H
#define SIXEYES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct sixeyes_port sixeyes_port;

/* Open a serial port such as "COM3" or "/dev/ttyACM0". Returns NULL on failure; see sixeyes_last_error(). */
sixeyes_port *sixeyes_open(const char *name);
void sixeyes_close(sixeyes_port *port);

/* Send one frame. Returns 0 on success, -1 on error. */
int sixeyes_write_frame(sixeyes_port *port, uint8_t type, uint8_t seq, const uint8_t *payload, size_t len);

/* Wait up to timeout_ms for one frame. Returns 1 (frame in the outputs), 0 (timeout), -1 (error),
 * or -2 (payload larger than `cap`; the frame is dropped). */
int sixeyes_read_frame(sixeyes_port *port, int timeout_ms, uint8_t *type, uint8_t *seq, uint8_t *payload, size_t cap,
                       size_t *len);

/* A short sentence describing the last error on this thread. */
const char *sixeyes_last_error(void);

#ifdef __cplusplus
}
#endif
#endif /* SIXEYES_H */
