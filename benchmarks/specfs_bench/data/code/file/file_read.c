#include "file.h"

void file_read(struct inode *node, unsigned offset, unsigned len, char *data) {
    struct indextb *tb = node->file;
    unsigned start_page = offset >> 12;
    unsigned end_page = (offset + len - 1) >> 12;
    unsigned i;
    
    for (i = start_page; i <= end_page; i++) {
        unsigned char *page = tb->index[i];
        unsigned page_offset = (i == start_page) ? offset & 0xfff : 0;
        unsigned copy_len = len;
        
        // Calculate how many bytes to copy from this page
        if (i == start_page) {
            copy_len = (len < (PG_SIZE - page_offset)) ? len : (PG_SIZE - page_offset);
        } else if (i == end_page) {
            copy_len = (offset + len) & 0xfff;
            if (copy_len == 0) copy_len = PG_SIZE;
        } else {
            copy_len = PG_SIZE;
        }
        
        // Copy the data from the page to the output buffer
        memcpy(data, page + page_offset, copy_len);
        data += copy_len;
        len -= copy_len;
    }
}