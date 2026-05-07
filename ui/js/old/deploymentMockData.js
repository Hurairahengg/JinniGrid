/* deploymentMockData.js — Runtime config defaults & dropdown options */

var DeploymentConfig = (function () {
  'use strict';

  var runtimeDefaults = {
    symbol: 'EURUSD',
    lot_size: 0.01,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
    bar_size_points: 100,
    max_bars_memory: 500,
  };

  var symbolOptions = [
    'EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD',
    'USDCHF','NZDUSD','XAUUSD','BTCUSD','USTEC', 'SPX500', 'DOW30', 'FTSE100'
  ];

  var tickLookbackUnits = ['minutes', 'hours', 'days'];

  return {
    runtimeDefaults: runtimeDefaults,
    symbolOptions: symbolOptions,
    tickLookbackUnits: tickLookbackUnits,
  };
})();