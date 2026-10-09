// Seamly2D's VGObject::flipTransform applied to random axes and points, with real Qt.
#include <QLineF>
#include <QPointF>
#include <QTransform>
#include <cstdio>
#include <random>
static QTransform flipTransform(const QLineF &axis) {
    QTransform transform;
    if (axis.isNull()) return transform;
    const QLineF axisOX = QLineF(axis.x2(), axis.y2(), axis.x2() + 100, axis.y2());
    const qreal angle = axis.angleTo(axisOX);
    const QPointF p2 = axis.p2();
    QTransform m;
    m.translate(p2.x(), p2.y()); m.rotate(-angle); m.translate(-p2.x(), -p2.y());
    transform *= m;
    m.reset();
    m.translate(p2.x(), p2.y()); m.scale(m.m11(), m.m22() * -1); m.translate(-p2.x(), -p2.y());
    transform *= m;
    m.reset();
    m.translate(p2.x(), p2.y()); m.rotate(-(360 - angle)); m.translate(-p2.x(), -p2.y());
    transform *= m;
    return transform;
}
int main() {
    std::mt19937_64 rng(2024);
    auto u = [&](double a, double b) { return std::uniform_real_distribution<double>(a, b)(rng); };
    for (int i = 0; i < 4000; ++i) {
        double x1 = u(-2000, 2000), y1 = u(-2000, 2000), x2 = u(-2000, 2000), y2 = u(-2000, 2000);
        if (i % 6 == 0) y2 = y1;            // horizontal axis
        if (i % 7 == 0) x2 = x1;            // vertical axis
        if (i % 10 == 0) { x2 = x1 + (i % 20 ? 100 : -100); y2 = y1 + (i % 20 ? 100 : -100); }
        if (i % 13 == 0) { x2 = x1; y2 = y1; }   // null axis
        double px = u(-3000, 3000), py = u(-3000, 3000);
        QLineF axis(x1, y1, x2, y2);
        QTransform t = flipTransform(axis);
        QPointF r = t.map(QPointF(px, py));
        std::printf("{\"a\":[%.17g,%.17g,%.17g,%.17g],\"p\":[%.17g,%.17g],\"r\":[%.17g,%.17g]}\n", x1, y1, x2, y2, px, py, r.x(), r.y());
    }
}
