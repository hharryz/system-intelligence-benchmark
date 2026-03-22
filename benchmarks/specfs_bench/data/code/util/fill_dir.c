#include "util.h"

void fill_dir(struct inode* inum, char** dircontent) {
    int i, j = 0;
    
    for (i = 0; i < DIRTB_NUM; i++) {
        struct entry* walk = inum->dir->tb[i];
        while (walk != NULL) {
            dircontent[j] = malloc_string(walk->name);
            j++;
            walk = walk->next;
        }
    }
    
    dircontent[j] = NULL;
}