/* deploymentMockData.js */

var DeploymentMockData = (function () {
  'use strict';

  var strategyMetadata = {
    name: 'MA Crossover RSI Filter',
    version: '1.2.0',
    type: 'Trend Following',
    description: 'Moving average crossover strategy with RSI filter for entry confirmation and dynamic position sizing.',
    requiredSymbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
    parameterCount: 7,
    lastModified: '2026-04-28',
    validationStatus: 'mock_validated'
  };

  var strategyParameters = [
    { key: 'fast_ma_period', label: 'Fast MA Period', type: 'int', defaultValue: 14, min: 2, max: 200, step: 1, description: 'Period for fast moving average' },
    { key: 'slow_ma_period', label: 'Slow MA Period', type: 'int', defaultValue: 50, min: 5, max: 500, step: 1, description: 'Period for slow moving average' },
    { key: 'rsi_period', label: 'RSI Period', type: 'int', defaultValue: 14, min: 2, max: 100, step: 1, description: 'RSI indicator period' },
    { key: 'stop_loss_points', label: 'Stop Loss (points)', type: 'float', defaultValue: 500.0, min: 10, max: 10000, step: 10, description: 'Stop loss distance in points' },
    { key: 'take_profit_points', label: 'Take Profit (points)', type: 'float', defaultValue: 1000.0, min: 10, max: 20000, step: 10, description: 'Take profit distance in points' },
    { key: 'trailing_stop_enabled', label: 'Trailing Stop', type: 'bool', defaultValue: false, min: null, max: null, step: null, description: 'Enable trailing stop loss' },
    { key: 'max_positions', label: 'Max Positions', type: 'int', defaultValue: 3, min: 1, max: 20, step: 1, description: 'Maximum number of simultaneous open positions' }
  ];

  var runtimeConfigDefaults = {
    symbol: 'EURUSD',
    lot_size: 0.01,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
    bar_size_points: 100,
    max_bars_memory: 500,
    max_spread: 3.0,
    magic_number: 100001,
    slippage: 3,
    execution_mode: 'dry_run',
    auto_start: false,
    allow_new_entries: true,
    close_existing: false
  };

  var symbolOptions = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'XAUUSD', 'BTCUSD'];

  var tickLookbackUnits = ['minutes', 'hours', 'days'];

  var executionModes = [
    { value: 'dry_run', label: 'Dry Run', disabled: false },
    { value: 'live', label: 'Live (Disabled)', disabled: true }
  ];

  return {
    strategyMetadata: strategyMetadata,
    strategyParameters: strategyParameters,
    runtimeConfigDefaults: runtimeConfigDefaults,
    symbolOptions: symbolOptions,
    tickLookbackUnits: tickLookbackUnits,
    executionModes: executionModes
  };
})();