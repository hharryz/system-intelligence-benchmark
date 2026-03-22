#include "file.h"

void file_clear(struct inode *node, unsigned start, unsigned len) {
    file_write(node, start, len, NULL);
}