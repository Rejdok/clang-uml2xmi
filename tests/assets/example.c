// Example C source file for testing method binding

#include <stdio.h>
#include <stdlib.h>

// Point struct definition
typedef struct {
    int x;
    int y;
} Point;

// Rectangle struct  
typedef struct {
    Point top_left;
    Point bottom_right;
} Rectangle;

// Color enum
typedef enum {
    RED,
    GREEN, 
    BLUE,
    BLACK,
    WHITE
} Color;

// Functions that should be bound to Point struct
void point_move(Point* p, int dx, int dy) {
    p->x += dx;
    p->y += dy;
}

void point_print(const Point* p) {
    printf("Point(%d, %d)\n", p->x, p->y);
}

int point_distance_squared(const Point* a, const Point* b) {
    int dx = a->x - b->x;
    int dy = a->y - b->y;
    return dx * dx + dy * dy;
}

Point point_create(int x, int y) {
    Point p = {x, y};
    return p;
}

// Functions that should be bound to Rectangle struct
void rect_init(Rectangle* rect, int x1, int y1, int x2, int y2) {
    rect->top_left.x = x1;
    rect->top_left.y = y1;
    rect->bottom_right.x = x2;
    rect->bottom_right.y = y2;
}

int rect_area(const Rectangle* rect) {
    int width = rect->bottom_right.x - rect->top_left.x;
    int height = rect->bottom_right.y - rect->top_left.y;
    return width * height;
}

void rect_print(const Rectangle* rect) {
    printf("Rectangle[(%d,%d) to (%d,%d)]\n", 
           rect->top_left.x, rect->top_left.y,
           rect->bottom_right.x, rect->bottom_right.y);
}

// Utility functions (should NOT be bound to any struct)
int max(int a, int b) {
    return (a > b) ? a : b;
}

int min(int a, int b) {
    return (a < b) ? a : b;
}

void init_graphics() {
    printf("Graphics system initialized\n");
}

void cleanup_resources() {
    printf("Resources cleaned up\n");
}

