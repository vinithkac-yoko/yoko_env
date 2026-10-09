// Emits real Qt QLineF results for random inputs as JSON lines (%.17g keeps every bit).
#include <QLineF>
#include <QPointF>
#include <cstdio>
#include <random>
static void pt(const char *k, const QPointF &p) { std::printf("\"%s\":[%.17g,%.17g],", k, p.x(), p.y()); }
int main(int argc, char **argv) {
    int n = argc > 1 ? std::atoi(argv[1]) : 3000;
    std::mt19937_64 rng(12345);
    auto u = [&](double a, double b) { return std::uniform_real_distribution<double>(a, b)(rng); };
    for (int i = 0; i < n; ++i) {
        // mix of "nice" and arbitrary values, like real patterns
        double x1 = (i % 3 == 0) ? 30.0 : u(-3000, 3000), y1 = (i % 3 == 0) ? 39.999874015748034 : u(-3000, 3000);
        double x2 = u(-3000, 3000), y2 = u(-3000, 3000);
        if (i % 5 == 0) { x2 = x1 + 100; y2 = y1; }           // the endLine seed line
        if (i % 7 == 0) { y2 = y1; }                           // horizontal
        if (i % 11 == 0) { x2 = x1; }                          // vertical
        double angle = (i % 4 == 0) ? 90.0 * (i % 9) : u(-720, 720);
        double len = u(0, 2500);
        double x3 = u(-3000, 3000), y3 = u(-3000, 3000), x4 = u(-3000, 3000), y4 = u(-3000, 3000);
        QLineF l(QPointF(x1, y1), QPointF(x2, y2)), m(QPointF(x3, y3), QPointF(x4, y4));
        std::printf("{\"i\":%d,", i);
        pt("p1", l.p1()); pt("p2", l.p2()); pt("q1", m.p1()); pt("q2", m.p2());
        std::printf("\"angle_in\":%.17g,\"len_in\":%.17g,", angle, len);
        std::printf("\"length\":%.17g,\"angle\":%.17g,\"angle_to\":%.17g,", l.length(), l.angle(), l.angleTo(m));
        QLineF a = l; a.setAngle(angle); pt("set_angle", a.p2());
        QLineF s = l; s.setLength(len); pt("set_length", s.p2());
        QLineF un = l.unitVector(); pt("unit", un.p2());
        QLineF nv = l.normalVector(); pt("normal", nv.p2());
        QPointF ip; QLineF::IntersectType t = l.intersects(m, &ip);
        std::printf("\"isect_type\":%d,", (int)t); pt("isect", ip);
        std::printf("\"end\":0}\n");
    }
}
