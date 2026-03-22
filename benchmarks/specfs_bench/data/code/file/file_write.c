#include "file.h"

void file_write(struct inode *node, unsigned offset, unsigned len, const char *data) {
    if (len == 0) {
        return;
    }
    
    unsigned current_offset = offset;
    unsigned remaining = len;
    unsigned page_index;
    unsigned page_offset;
    unsigned copy_len;
    
    while (remaining > 0) {
        page_index = current_offset / PG_SIZE;
        page_offset = current_offset % PG_SIZE;
        copy_len = (remaining < PG_SIZE - page_offset) ? remaining : (PG_SIZE - page_offset);
        
        // Allocate page if data is NULL and page is not allocated
        if (data == NULL && node->file->index[page_index] == NULL) {
            node->file->index[page_index] = (unsigned char *)malloc(PG_SIZE);
            if (node->file->index[page_index] != NULL) {
                memset(node->file->index[page_index], 0, PG_SIZE);
            }
        }
        
        // Handle writing
        if (data == NULL) {
            // Zero-initialize the range
            if (node->file->index[page_index] != NULL) {
                memset(node->file->index[page_index] + page_offset, 0, copy_len);
            }
        } else {
            // Copy data from buffer
            if (node->file->index[page_index] != NULL) {
                memcpy(node->file->index[page_index] + page_offset, data, copy_len);
            }
        }
        
        current_offset += copy_len;
        remaining -= copy_len;
        data += copy_len;
    }
}