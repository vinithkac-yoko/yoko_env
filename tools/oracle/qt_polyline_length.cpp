#include <QPainterPath>
#include <QPointF>
#include <QLineF>
#include <cstdio>
#include <random>
int main() {
    std::mt19937_64 rng(777);
    auto u = [&](double a, double b) { return std::uniform_real_distribution<double>(a, b)(rng); };
    for (int t = 0; t < 2000; ++t) {
        int n = 2 + (t % 60);
        QPainterPath path; QVector<QPointF> pts;
        for (int i = 0; i < n; ++i) { QPointF p(u(-2000, 2000), u(-2000, 2000)); pts << p; }
        path.moveTo(pts[0]);
        for (int i = 1; i < n; ++i) path.lineTo(pts[i]);
        std::printf("{\"n\":%d,\"len\":%.17g,\"pts\":[", n, path.length());
        for (int i = 0; i < n; ++i) std::printf("%s[%.17g,%.17g]", i ? "," : "", pts[i].x(), pts[i].y());
        std::printf("]}\n");
    }
}
