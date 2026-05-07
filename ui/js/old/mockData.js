/* mockData.js */

var MockData = (function () {
  'use strict';

  var portfolioStats = {
    totalBalance: 248750.00,
    totalEquity: 251320.45,
    floatingPnl: 2570.45,
    dailyPnl: 1847.30,
    openPositions: 12,
    realizedPnl: 18432.60,
    marginUsage: 34.7,
    winRate: 68.5
  };

  var equityCurve = (function () {
    var points = [];
    var startDate = new Date(2026, 1, 5);
    var value = 200000;
    // Seeded-style random using simple LCG
    var seed = 42;
    function seededRandom() {
      seed = (seed * 16807 + 0) % 2147483647;
      return (seed - 1) / 2147483646;
    }
    for (var i = 0; i < 90; i++) {
      var date = new Date(startDate);
      date.setDate(date.getDate() + i);
      value += (seededRandom() - 0.42) * 2000;
      if (value < 180000) value = 180000;
      points.push({
        date: date.toISOString().slice(0, 10),
        value: Math.round(value * 100) / 100
      });
    }
    return points;
  })();

  return {
    portfolioStats: portfolioStats,
    equityCurve: equityCurve
  };
})();
