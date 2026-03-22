#include "util.h"

void dispose_inode(struct inode* inum) {
    if (inum == NULL) {
        return;
    }

    // Destroy the mutex
    if (inum->impl != NULL) {
        mcs_mutex_destroy(inum->impl);
    }

    // Free directory table if it's a directory
    if (inum->mode == DIR_MODE && inum->dir != NULL) {
        for (int i = 0; i < DIRTB_NUM; i++) {
            struct entry *entry = inum->dir->tb[i];
            while (entry != NULL) {
                struct entry *next = entry->next;
                if (entry->name != NULL) {
                    free(entry->name);
                }
                free(entry);
                entry = next;
            }
        }
        free(inum->dir);
    }

    // Free index table if it's a file
    if (inum->mode == FILE_MODE && inum->file != NULL) {
        for (int i = 0; i < INDEXTB_NUM; i++) {
            if (inum->file->index[i] != NULL) {
                free(inum->file->index[i]);
            }
        }
        free(inum->file);
    }

    // Free the inode structure itself
    free(inum);
}