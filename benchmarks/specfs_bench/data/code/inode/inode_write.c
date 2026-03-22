#include "inode.h"

unsigned inode_write(struct inode* node, const char* buffer, unsigned len, unsigned offset) {
    if (len == 0) {
        return 0;
    }

    // Calculate new size after write
    unsigned new_size = offset + len;
    if (new_size > MAX_FILE_SIZE) {
        new_size = MAX_FILE_SIZE;
    }

    // If new size is greater than current size, allocate and clear space
    if (new_size > node->size) {
        unsigned alloc_len = new_size - node->size;
        file_allocate(node, node->size, alloc_len);
        file_clear(node, node->size, alloc_len);
        node->size = new_size;
    }

    // Write the data to the file at the specified offset
    // Note: file_write handles cases where offset+len may exceed current size,
    // but we've already ensured allocation up to new_size, so it's safe
    file_write(node, offset, len, buffer);

    return len;
}