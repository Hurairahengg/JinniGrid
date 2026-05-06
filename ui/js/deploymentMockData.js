var DeploymentMockData = (function () {
  'use strict';

  var strategyMetadata = {
    name: 'MA Crossover RSI Filter',
    version: '1.2.0',
    type: 'Trend Following',
    description: 'Moving average crossover strategy with RSI filter for entry confirmation and dynamic position sizing.',
    requiredSymbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
    parameterCount: 10,
    lastModified: '2026-04-28',
    validationStatus: 'mock_validated'
  };

  var strategyParameters = [
    { key: 'fast_ma_period', label: 'Fast MA Period', type: 'int', defaultValue: 14, min: 2, max: 200, step: 1, description: 'Period for fast moving average' },
    { key: 'slow_ma_period', label: 'Slow MA Period', type: 'int', defaultValue: 50, min: 5, max: 500, step: 1, description: 'Period for slow moving average' },
    { key: 'rsi_period', label: 'RSI Period', type: 'int', defaultValue: 14, min: 2, max: 100, step: 1, description: 'RSI indicator period' },
    { key: 'rsi_buy_level', label: 'RSI Buy Level', type: 'float', defaultValue: 30.0, min: 0, max: 100, step: 0.5, description: 'RSI level below which to consider buy signals' },
    { key: 'rsi_sell_level', label: 'RSI Sell Level', type: 'float', defaultValue: 70.0, min: 0, max: 100, step: 0.5, description: 'RSI level above which to consider sell signals' },
    { key: 'stop_loss_pips', label: 'Stop Loss (pips)', type: 'float', defaultValue: 50.0, min: 5, max: 500, step: 1, description: 'Stop loss distance in pips' },
    { key: 'take_profit_pips', label: 'Take Profit (pips)', type: 'float', defaultValue: 100.0, min: 10, max: 1000, step: 1, description: 'Take profit distance in pips' },
    { key: 'trailing_stop_enabled', label: 'Trailing Stop', type: 'bool', defaultValue: false, min: null, max: null, step: null, description: 'Enable trailing stop loss' },
    { key: 'risk_per_trade', label: 'Risk Per Trade (%)', type: 'float', defaultValue: 1.0, min: 0.1, max: 10, step: 0.1, description: 'Percentage of account balance to risk per trade' },
    { key: 'max_positions', label: 'Max Positions', type: 'int', defaultValue: 3, min: 1, max: 20, step: 1, description: 'Maximum number of simultaneous open positions' }
  ];

  var runtimeConfigDefaults = {
    symbol: 'EURUSD', lot_size: 0.01, timeframe: 'H1', max_spread: 3.0,
    magic_number: 100001, slippage: 3, execution_mode: 'demo',
    auto_start: false, allow_new_entries: true, close_existing: false
  };

  var symbolOptions = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'XAUUSD', 'BTCUSD'];
  var timeframeOptions = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1'];
  var executionModes = [
    { value: 'demo', label: 'Demo Mode', disabled: false },
    { value: 'live', label: 'Live Mode (Disabled)', disabled: true }
  ];

  return {
    strategyMetadata: strategyMetadata,
    strategyParameters: strategyParameters,
    runtimeConfigDefaults: runtimeConfigDefaults,
    symbolOptions: symbolOptions,
    timeframeOptions: timeframeOptions,
    executionModes: executionModes
  };
})();
