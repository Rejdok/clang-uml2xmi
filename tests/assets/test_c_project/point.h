// Point struct definition
#ifndef POINT_H
#define POINT_H

typedef struct {
    int x;
    int y;
} Point;

// Function declarations
void point_move(Point* p, int dx, int dy);
void point_print(const Point* p);
int point_distance_squared(const Point* a, const Point* b);
Point point_create(int x, int y);

#endif // POINT_H
