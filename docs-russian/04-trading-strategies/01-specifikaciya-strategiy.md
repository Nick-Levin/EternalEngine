# Спецификации торговых стратегий — Техническая документация

## Содержание
1. [Стратегия следования за трендом](#1-стратегия-следования-за-трендом)
2. [Арбитраж ставок финансирования](#2-арбитраж-ставок-финансирования)
3. [Сеточная торговля](#3-сеточная-торговля)
4. [Стратегия DCA/Ребалансировки](#4-стратегия-dcareбалансировки)
5. [Тактическое/Кризисное развертывание](#5-тактическоекризисное-развертывание)
6. [Фреймворк управления рисками](#6-фреймворк-управления-рисками)
7. [Справочник по реализации](#7-справочник-по-реализации)

---

## 1. Стратегия следования за трендом

### 1.1 Обзор
Следование за трендом захватывает устойчивые направленные движения с использованием подтверждения моментума на нескольких таймфреймах. Эта стратегия идентифицирует установленные тренды и следует за ними до появления сигналов разворота.

### 1.2 Параметры индикаторов

| Индикатор | Параметр | Значение по умолчанию | Описание |
|-----------|----------|----------------------|----------|
| Быстрая EMA | Период | 9 | Краткосрочное направление тренда |
| Медленная EMA | Период | 21 | Долгосрочное направление тренда |
| ATR | Период | 14 | Измерение волатильности для стоп-лосса |
| ADX | Период | 14 | Подтверждение силы тренда |
| RSI | Период | 14 | Условия перекупленности/перепроданности |
| Объем SMA | Период | 20 | Подтверждение объема |

### 1.3 Спецификации таймфреймов

```yaml
Основной таймфрейм: 4h      # Решения о входе/выходе
Подтверждающий TF: 1d       # Биас направления тренда
Исполнительский TF: 1h      # Точное время входа
Объемный TF: 4h             # Анализ объема
```

### 1.4 Правила входа

#### Длинный вход (Сигнал покупки)
```
ТРЕБУЕМЫЕ_УСЛОВИЯ:
    1. Fast_EMA(9) > Slow_EMA(21) [Бычье выравнивание]
    2. ADX(14) > 25 [Подтвержден сильный тренд]
    3. Close > Fast_EMA(9) [Цена выше краткосрочного тренда]
    4. Volume > Volume_SMA(20) * 1.2 [Подтверждение объема]
    5. RSI(14) ∈ (30, 70) [Не экстремум]
    
ОПЦИОНАЛЬНЫЕ_ФИЛЬТРЫ:
    - Выравнивание EMA на старшем таймфрейме (1d) совпадает
    - Нет сопротивления в пределах 2x ATR
```

#### Короткий вход (Сигнал продажи)
```
ТРЕБУЕМЫЕ_УСЛОВИЯ:
    1. Fast_EMA(9) < Slow_EMA(21) [Медвежье выравнивание]
    2. ADX(14) > 25 [Подтвержден сильный тренд]
    3. Close < Fast_EMA(9) [Цена ниже краткосрочного тренда]
    4. Volume > Volume_SMA(20) * 1.2 [Подтверждение объема]
    5. RSI(14) ∈ (30, 70) [Не экстремум]
```

### 1.5 Правила выхода

#### Take Profit (Многоуровневый выход)
```python
# Стратегия многоуровневой фиксации прибыли
profit_targets = {
    'tp1': {'pct': 1.5, 'size': 0.30},   # 30% на 1.5R
    'tp2': {'pct': 3.0, 'size': 0.40},   # 40% на 3R
    'tp3': {'pct': 5.0, 'size': 0.30},   # 30% на 5R (бегунок)
}

# Активация трейлинг-стопа
trailing_activation = 2.0  # Активировать после прибыли 2R
trailing_distance = 1.5 * ATR(14)  # Трейл на 1.5 ATR
```

#### Stop Loss (На основе ATR)
```python
def calculate_stop_loss(entry_price, side, atr14, multiplier=2.0):
    """
    Расчет ATR-based стоп-лосса.
    
    Формула:
        LONG_STOP = Entry - (ATR × Multiplier)
        SHORT_STOP = Entry + (ATR × Multiplier)
    """
    atr_distance = atr14 * multiplier
    
    if side == "long":
        return entry_price - atr_distance
    else:
        return entry_price + atr_distance

# Риск на сделку: 1% портфеля
risk_per_trade_pct = 0.01
```

### 1.6 Формула размера позиции

```python
def calculate_position_size(portfolio_value, entry_price, stop_price, risk_pct=0.01):
    """
    Размер позиции, вдохновленный критерием Келли.
    
    Формула:
        RISK_AMOUNT = Portfolio × Risk_Pct
        STOP_DISTANCE = |Entry - Stop|
        POSITION_SIZE = RISK_AMOUNT / STOP_DISTANCE
    """
    risk_amount = portfolio_value * risk_pct
    stop_distance = abs(entry_price - stop_price)
    
    if stop_distance == 0:
        return 0
    
    quantity = risk_amount / stop_distance
    position_value = quantity * entry_price
    
    # Максимальный лимит позиции (5% портфеля)
    max_position_value = portfolio_value * 0.05
    
    if position_value > max_position_value:
        quantity = max_position_value / entry_price
    
    return quantity

# Альтернатива: Фиксированное фракционное размещение
def fixed_fractional_size(portfolio_value, confidence, base_risk=0.01):
    """
    Корректировка размера на основе уверенности сигнала.
    """
    confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x до 1.0x
    return portfolio_value * base_risk * confidence_multiplier
```

### 1.7 Правила управления рисками

| Правило | Параметр | Действие |
|---------|----------|----------|
| Макс размер позиции | 5% портфеля | Жесткий лимит на сделку |
| Макс одновременных трендов | 3 позиции | Ограничение корреляционного риска |
| Макс дневной убыток | 2% портфеля | Остановка торговли на день |
| Макс недельный убыток | 5% портфеля | Остановка торговли на неделю |
| Лимит корреляции | ρ > 0.7 | Не добавлять коррелированные позиции |
| Прерыватель просадки | 10% от пика | Сократить размер на 50% |

### 1.8 Псевдокод реализации

```python
class TrendFollowingStrategy:
    
    def analyze(self, market_data):
        signals = []
        
        for symbol in self.symbols:
            # Расчет индикаторов
            df = market_data[symbol]
            df['fast_ema'] = EMA(df.close, 9)
            df['slow_ema'] = EMA(df.close, 21)
            df['atr'] = ATR(df, 14)
            df['adx'] = ADX(df, 14)
            df['rsi'] = RSI(df.close, 14)
            df['vol_sma'] = SMA(df.volume, 20)
            
            current = df.iloc[-1]
            
            # Проверка длинного входа
            if (current.fast_ema > current.slow_ema and      # Выравнивание тренда
                current.adx > 25 and                          # Сильный тренд
                current.close > current.fast_ema and          # Подтверждение цены
                current.volume > current.vol_sma * 1.2 and    # Всплеск объема
                30 < current.rsi < 70):                       # Не экстремум
                
                if not self.has_position(symbol):
                    stop_price = current.close - (current.atr * 2.0)
                    size = self.calculate_position_size(
                        self.portfolio_value,
                        current.close,
                        stop_price
                    )
                    signals.append(BuySignal(symbol, size, stop_price))
            
            # Проверки выхода для существующих позиций
            for position in self.open_positions:
                pnl_pct = position.unrealized_pnl_pct
                
                # Многоуровневая фиксация прибыли
                if pnl_pct >= 1.5 and not position.tp1_hit:
                    signals.append(PartialClose(position, 0.30))
                    position.tp1_hit = True
                elif pnl_pct >= 3.0 and not position.tp2_hit:
                    signals.append(PartialClose(position, 0.40))
                    position.tp2_hit = True
                    position.activate_trailing_stop(current.atr * 1.5)
                
                # Выход при развороте тренда
                if position.side == "long" and current.fast_ema < current.slow_ema:
                    signals.append(ClosePosition(position, reason="trend_reversal"))
        
        return signals
```

---

## 2. Арбитраж ставок финансирования

### 2.1 Обзор
Арбитраж ставок финансирования захватывает периодические выплаты финансирования между перпетуальными фьючерсами и спотовыми рынками, поддерживая дельта-нейтральную экспозицию.

### 2.2 Структура рынка

```
ПЕРПЕТУАЛЬНЫЕ ФЬЮЧЕРСЫ:
    - Нет даты экспирации
    - Финансирование выплачивается каждые 8 часов (00:00, 08:00, 16:00 UTC)
    - Ставка финансирования > 0: Лонгисты платят шортистам
    - Ставка финансирования < 0: Шортисты платят лонгистам

СПОТОВЫЙ РЫНОК:
    - Немедленное расчет
    - Нет затрат на финансирование
    - Требует полного капитала
```

### 2.3 Конструирование дельта-нейтральной позиции

```python
def construct_delta_neutral_position(symbol, funding_rate, capital):
    """
    Конструирование рыночно-нейтральной арбитражной позиции.
    
    Структура позиции:
        SPOT:   +1.0 BTC (Лонг спот)
        FUTURE: -1.0 BTC (Шорт перп)
        
    Чистая дельта: 0 (Движения цены компенсируются)
    Доход от финансирования: |Ставка_финансирования| × Номинал каждые 8ч
    """
    
    # Расчет размеров позиций
    spot_price = get_spot_price(symbol)
    perp_price = get_perp_price(symbol)
    
    # Проверка базисного риска
    basis = (perp_price - spot_price) / spot_price
    if abs(basis) > 0.005:  # Макс 0.5% базиса
        raise BasisRiskExceeded(f"Базис: {basis:.4%}")
    
    # Размер позиции
    max_position_value = capital * 0.95  # 5% буфер для маржи
    quantity = max_position_value / spot_price
    
    return {
        'spot': {'side': 'buy', 'quantity': quantity, 'price': spot_price},
        'perp': {'side': 'sell', 'quantity': quantity, 'price': perp_price},
        'expected_funding': quantity * perp_price * abs(funding_rate),
        'basis_at_entry': basis
    }
```

### 2.4 Триггеры входа

| Тип триггера | Условие | Минимальный порог |
|--------------|---------|-------------------|
| Высокий положительный | Финансирование > 0 | +0.01% за 8ч (0.03%/день) |
| Высокий отрицательный | Финансирование < 0 | -0.01% за 8ч |
| Экстремальный | Финансирование > 3σ | 95-й процентиль исторических |
| Предиктивный | Предсказанный > Текущий | На основе индекса премии |

```python
ENTRY_LOGIC:
    # Годовой порог финансирования
    ANNUALIZED_THRESHOLD = 0.10  # 10% годовых
    
    # Расчет годовой ставки
    periods_per_year = 365 * 3  # 3 периода финансирования в день
    annualized_rate = funding_rate * periods_per_year
    
    # Условия входа
    if annualized_rate > ANNUALIZED_THRESHOLD:
        # Положительное финансирование: Лонг спот, Шорт перп
        direction = "positive_carry"
    elif annualized_rate < -ANNUALIZED_THRESHOLD:
        # Отрицательное финансирование: Шорт спот, Лонг перп
        direction = "negative_carry"
```

### 2.5 Триггеры выхода

```python
EXIT_CONDITIONS = {
    'funding_compression': {
        'description': 'Ставка финансирования нормализовалась',
        'condition': 'abs(current_funding) < entry_threshold / 2'
    },
    'basis_expansion': {
        'description': 'Спред спот-перп слишком широкий',
        'condition': 'abs(basis) > 1.0%',
        'action': 'Немедленная ликвидация'
    },
    'margin_call_risk': {
        'description': 'Перп позиция близка к ликвидации',
        'condition': 'margin_ratio < 20%',
        'action': 'Сократить позицию или добавить маржу'
    },
    'time_decay': {
        'description': 'Позиция удерживается слишком долго без прибыли',
        'condition': 'days_held > 7 and unrealized_pnl < 0',
        'action': 'Рассмотреть выход'
    }
}
```

### 2.6 Правила мониторинга позиций

```python
class FundingArbitrageMonitor:
    
    CHECK_INTERVAL_MINUTES = 5
    
    def monitor_position(self, position):
        alerts = []
        
        # 1. Мониторинг базиса
        current_basis = self.get_current_basis(position.symbol)
        basis_change = current_basis - position.entry_basis
        
        if abs(basis_change) > 0.005:  # 0.5% движение базиса
            alerts.append({
                'type': 'basis_warning',
                'severity': 'high',
                'message': f'Базис сдвинулся на {basis_change:.4%}'
            })
        
        # 2. Мониторинг маржи (нога перп)
        margin_ratio = self.get_margin_ratio(position.perp_leg)
        if margin_ratio < 0.30:  # 30% коэффициент маржи
            alerts.append({
                'type': 'margin_warning',
                'severity': 'critical',
                'message': f'Коэффициент маржи: {margin_ratio:.2%}'
            })
        
        # 3. Отслеживание накопленного финансирования
        accumulated_funding = self.calculate_accumulated_funding(position)
        unrealized_pnl = self.calculate_unrealized_pnl(position)
        
        total_return = accumulated_funding + unrealized_pnl
        days_held = (now - position.entry_time).days
        
        # Проверка точки безубыточности
        if total_return < 0 and days_held > 3:
            alerts.append({
                'type': 'profitability_warning',
                'severity': 'medium',
                'message': f'Убыточно после {days_held} дней'
            })
        
        return alerts
```

### 2.7 Логика ребалансировки

```python
def rebalance_position(position, threshold_pct=0.02):
    """
    Ребалансировка при отклонении хедж-коэффициента.
    
    Причины отклонения:
        - Разные движения цены (изменение базиса)
        - Частичное исполнение
        - Корректировки маржи на ноге перп
    """
    spot_value = position.spot.quantity * current_spot_price
    perp_value = position.perp.quantity * current_perp_price
    
    # Расчет отклонения хедж-коэффициента
    deviation = abs(spot_value - perp_value) / ((spot_value + perp_value) / 2)
    
    if deviation > threshold_pct:
        # Нужна ребалансировка
        if spot_value > perp_value:
            # Уменьшить спот или увеличить перп
            rebalance_amount = (spot_value - perp_value) / 2
            return {
                'action': 'reduce_spot',
                'amount': rebalance_amount / current_spot_price
            }
        else:
            rebalance_amount = (perp_value - spot_value) / 2
            return {
                'action': 'reduce_perp',
                'amount': rebalance_amount / current_perp_price
            }
    
    return {'action': 'no_action'}
```

### 2.8 Риск расширения базиса

| Фактор риска | Описание | Митигация |
|--------------|----------|-----------|
| **Переворот Контанго/Бэквордация** | Спред перп-спот меняет знак | Макс 0.5% базиса при входе, стоп на 1% |
| **Несоответствие ликвидности** | Невозможность выйти из одной ноги | Использовать только ликвидные пары (BTC, ETH) |
| **Риск биржи** | Неисполнение обязательств контрагентом | Разделить между 2+ биржами |
| **Переворот ставки финансирования** | Ставка меняет знак | Выход если ставка пересекает ноль |
| **Маржин-колл** | Ликвидация перп позиции | Поддерживать коэффициент маржи 200%+ |

```python
# Расчет базисного риска
def calculate_basis_risk_metrics(position):
    spot_price = get_spot_price(position.symbol)
    perp_price = get_perp_price(position.symbol)
    
    basis = perp_price - spot_price
    basis_pct = basis / spot_price
    
    # P&L по рыночной оценке от базиса
    basis_pnl = basis_pct * position.notional_value
    
    # P&L от финансирования (накопленный)
    funding_pnl = sum(position.funding_payments)
    
    # Общий P&L
    total_pnl = basis_pnl + funding_pnl
    
    # Метрики риска
    return {
        'basis_pnl': basis_pnl,
        'funding_pnl': funding_pnl,
        'total_pnl': total_pnl,
        'basis_breakeven_days': abs(basis_pnl) / (abs(position.hourly_funding) * 3),
        'max_adverse_basis': calculate_var_basis(position.symbol, confidence=0.95)
    }
```

---

## 3. Сеточная торговля

### 3.1 Обзор
Сеточная торговля использует колебания цены в определенном диапазоне, размещая ордера на покупку ниже и на продажу выше текущей цены.

### 3.2 Расчеты расстояний сетки

#### Арифметическая сетка (Равные ценовые интервалы)
```python
def calculate_arithmetic_grid(center_price, grid_levels, grid_range_pct):
    """
    Равное ценовое расстояние между уровнями.
    
    Формула:
        SPACING = (Center × Range%) / Levels
        Level_i = Center ± (i × Spacing)
    """
    total_range = center_price * (grid_range_pct / 100)
    spacing = total_range / grid_levels
    
    buy_levels = [center_price - (i * spacing) for i in range(1, grid_levels + 1)]
    sell_levels = [center_price + (i * spacing) for i in range(1, grid_levels + 1)]
    
    return {'buy_levels': buy_levels, 'sell_levels': sell_levels, 'spacing': spacing}
```

#### Геометрическая сетка (Равные процентные интервалы)
```python
def calculate_geometric_grid(center_price, grid_levels, grid_spacing_pct):
    """
    Равное процентное расстояние между уровнями.
    
    Формула:
        Level_i = Center × (1 ± Spacing%)^i
    """
    spacing_factor = 1 + (grid_spacing_pct / 100)
    
    buy_levels = [center_price / (spacing_factor ** i) for i in range(1, grid_levels + 1)]
    sell_levels = [center_price * (spacing_factor ** i) for i in range(1, grid_levels + 1)]
    
    return {'buy_levels': buy_levels, 'sell_levels': sell_levels}
```

### 3.3 Лимиты позиций на уровень сетки

```python
GRID_RISK_PARAMETERS = {
    'max_total_investment_pct': 50.0,    # Макс 50% портфеля в сетке
    'max_position_per_level_pct': 5.0,   # Макс 5% на уровень сетки
    'grid_levels': 10,                    # Количество уровней сетки
    'grid_spacing_pct': 1.0,              # 1% между уровнями (геометрический)
    'total_range_pct': 20.0,              # ±10% от центра (арифметический)
}

def calculate_grid_allocation(portfolio_value, num_levels, spacing_type='geometric'):
    """
    Расчет инвестиций на уровень сетки.
    
    Стратегии:
        - EQUAL: Одинаковая сумма на каждом уровне
        - PYRAMID: Больше на внешних уровнях (уклон к возврату к среднему)
        - REVERSE_PYRAMID: Больше на внутренних уровнях (уклон к тренду)
    """
    max_investment = portfolio_value * (GRID_RISK_PARAMETERS['max_total_investment_pct'] / 100)
    
    # Равный вес
    if spacing_type == 'equal':
        per_level = max_investment / num_levels
        return [per_level] * num_levels
    
    # Пирамида (обратный вес — агрессивнее на экстремумах)
    elif spacing_type == 'pyramid':
        weights = list(range(1, num_levels + 1))  # 1, 2, 3, ...
        total_weight = sum(weights)
        return [max_investment * (w / total_weight) for w in weights]
    
    # Обратная пирамида (более консервативная)
    elif spacing_type == 'reverse_pyramid':
        weights = list(range(num_levels, 0, -1))  # ..., 3, 2, 1
        total_weight = sum(weights)
        return [max_investment * (w / total_weight) for w in weights]
```

### 3.4 Условия сброса сетки

```python
GRID_RESET_TRIGGERS = {
    'price_outside_range': {
        'condition': 'price < lower_stop OR price > upper_stop',
        'lower_stop': 'center × (1 - range% - buffer%)',
        'upper_stop': 'center × (1 + range% + buffer%)',
        'buffer_pct': 2.0,  # 2% буфер за сеткой
        'action': 'Закрыть все, сбросить сетку в новом центре'
    },
    'time_based': {
        'condition': 'grid_age > max_grid_age',
        'max_grid_age_hours': 168,  # 1 неделя
        'action': 'Оценить прибыльность сетки, сбросить при необходимости'
    },
    'volatility_expansion': {
        'condition': 'atr_14 > grid_range / 4',
        'action': 'Расширить шаг сетки или приостановить'
    },
    'profit_target': {
        'condition': 'grid_pnl > target_pnl',
        'target_pnl_pct': 5.0,
        'action': 'Сбросить сетку для фиксации прибыли'
    }
}

def should_reset_grid(grid_state, current_price, current_atr):
    """Определить, нужен ли сброс сетки."""
    
    # 1. Цена вне диапазона
    if current_price < grid_state.lower_stop or current_price > grid_state.upper_stop:
        return {'reset': True, 'reason': 'price_outside_range'}
    
    # 2. Сброс по времени
    grid_age_hours = (datetime.utcnow() - grid_state.created_at).total_seconds() / 3600
    if grid_age_hours > GRID_RESET_TRIGGERS['time_based']['max_grid_age_hours']:
        # Сбрасывать только если прибыльно
        if grid_state.total_pnl > 0:
            return {'reset': True, 'reason': 'time_based_profitable'}
    
    # 3. Расширение волатильности
    grid_range = grid_state.upper_bound - grid_state.lower_bound
    if current_atr > grid_range / 4:
        return {'reset': True, 'reason': 'volatility_expansion'}
    
    return {'reset': False}
```

### 3.5 Контроль просадки

```python
GRID_DRAWDOWN_CONTROLS = {
    'max_grid_drawdown_pct': 10.0,      # Макс убыток до аварийной остановки
    'daily_grid_loss_limit_pct': 3.0,   # Дневной лимит убытка
    'max_uncovered_exposure': 2,        # Макс уровней с открытыми ордерами на покупку
    'hedge_on_breakout': True,          # Хеджировать при пробое диапазона
}

def calculate_grid_drawdown(grid_state, current_price):
    """
    Расчет просадки в худшем сценарии.
    
    Предполагает, что все ордера на покупку исполняются и цена падает до lower_stop.
    """
    # Стоимость неисполненных ордеров на покупку
    pending_buy_value = sum(
        level['quantity'] * level['price'] 
        for level in grid_state.pending_buys
    )
    
    # Текущая стоимость позиции по текущей цене
    current_position_value = grid_state.total_quantity * current_price
    
    # Стоимость в нижнем стопе (худший случай)
    worst_case_value = grid_state.total_quantity * grid_state.lower_stop
    
    # Общие вложения
    total_invested = grid_state.invested_capital + pending_buy_value
    
    # Расчет просадки
    paper_loss = current_position_value - worst_case_value
    drawdown_pct = paper_loss / total_invested * 100
    
    return {
        'current_drawdown_pct': drawdown_pct,
        'max_theoretical_loss': paper_loss + pending_buy_value * 0.5,
        'margin_of_safety': (current_price - grid_state.lower_stop) / current_price * 100
    }

# Динамический хедж при пробое
def hedge_breakout(grid_state, current_price):
    """
    При пробое диапазона сетки, хеджировать противоположной позицией
    для ограничения дальнейших убытков.
    """
    if current_price > grid_state.upper_stop:
        # Пробой вверх — хеджировать лонгом
        hedge_size = grid_state.total_quantity * 0.5  # 50% хедж
        return {'action': 'buy', 'quantity': hedge_size, 'reason': 'upper_breakout_hedge'}
    
    elif current_price < grid_state.lower_stop:
        # Пробой вниз — хеджировать шортом
        hedge_size = grid_state.total_quantity * 0.5
        return {'action': 'sell', 'quantity': hedge_size, 'reason': 'lower_breakout_hedge'}
    
    return {'action': 'none'}
```

### 3.6 Псевдокод реализации сетки

```python
class GridTradingStrategy:
    
    def __init__(self, symbols, grid_levels=10, spacing_pct=1.0):
        self.grid_levels = grid_levels
        self.spacing_pct = spacing_pct
        self.active_grids = {}  # symbol -> grid_state
    
    def create_grid(self, symbol, center_price):
        """Инициализация новой сетки вокруг центральной цены."""
        spacing = center_price * (self.spacing_pct / 100)
        
        grid = {
            'center_price': center_price,
            'buy_levels': [center_price - (i * spacing) for i in range(1, self.grid_levels + 1)],
            'sell_levels': [center_price + (i * spacing) for i in range(1, self.grid_levels + 1)],
            'lower_stop': center_price * 0.80,   # -20% стоп
            'upper_stop': center_price * 1.20,   # +20% стоп
            'orders': {},  # level_price -> order_id
            'filled_buys': [],  # Отслеживание заполненных уровней покупки
            'created_at': datetime.utcnow()
        }
        
        # Размещение начальных ордеров
        for level in grid['buy_levels']:
            order = self.place_limit_buy(symbol, level, self.get_quantity_for_level())
            grid['orders'][level] = order.id
        
        for level in grid['sell_levels']:
            order = self.place_limit_sell(symbol, level, self.get_quantity_for_level())
            grid['orders'][level] = order.id
        
        return grid
    
    def on_fill(self, symbol, price, side):
        """Обработка исполнения ордера — размещение противоположного ордера."""
        grid = self.active_grids[symbol]
        
        if side == 'buy':
            grid['filled_buys'].append(price)
            # Разместить ордер на продажу на уровень выше
            sell_price = price * (1 + self.spacing_pct / 100)
            if sell_price <= grid['upper_stop']:
                self.place_limit_sell(symbol, sell_price, self.get_quantity_for_level())
        
        elif side == 'sell':
            # Разместить ордер на покупку на уровень ниже
            buy_price = price / (1 + self.spacing_pct / 100)
            if buy_price >= grid['lower_stop']:
                self.place_limit_buy(symbol, buy_price, self.get_quantity_for_level())
    
    def analyze(self, market_data):
        """Основной цикл анализа."""
        signals = []
        
        for symbol in self.symbols:
            current_price = market_data[symbol].close
            
            # Проверка, нужен ли сброс сетки
            if symbol in self.active_grids:
                reset_check = should_reset_grid(
                    self.active_grids[symbol], 
                    current_price,
                    market_data[symbol].atr
                )
                
                if reset_check['reset']:
                    signals.append(GridResetSignal(symbol, reset_check['reason']))
                    del self.active_grids[symbol]
            
            # Создание новой сетки если нет активной
            if symbol not in self.active_grids:
                grid = self.create_grid(symbol, current_price)
                self.active_grids[symbol] = grid
                signals.append(GridCreatedSignal(symbol, grid))
        
        return signals
```

---

## 4. Стратегия DCA/Ребалансировки

### 4.1 Обзор
Усреднение стоимости доллара (DCA) снижает риск тайминга, инвестируя фиксированные суммы через регулярные интервалы. Ребалансировка поддерживает целевое распределение портфеля.

### 4.2 Параметры DCA

```yaml
DCA_CONFIGURATION:
    interval_hours: 24              # Время между покупками
    amount_usdt: 100.0              # Фиксированная сумма USD на покупку
    symbols: ['BTCUSDT', 'ETHUSDT'] # Целевые активы
    max_slippage_pct: 0.5           # Макс допустимое проскальзывание
    order_type: 'market'            # Рыночные или лимитные ордера
    
ADVANCED_DCA:
    volatility_adjustment: true     # Увеличить сумму при высокой волатильности
    fear_greed_trigger: true        # Дополнительные покупки при экстремальном страхе (< 20)
    max_weekly_investment: 1000.0   # Недельный лимит
```

### 4.3 Частота и пороги ребалансировки

```python
REBALANCING_CONFIG = {
    # Настройки частоты
    'frequency': {
        'type': 'threshold',        # 'time' или 'threshold' based
        'time_interval_days': 30,   # Если по времени
        'threshold_pct': 5.0,       # Ребалансировать при отклонении 5%
    },
    
    # Целевые распределения
    'target_allocations': {
        'BTC': 0.50,    # 50% Биткоин
        'ETH': 0.30,    # 30% Эфириум
        'USDT': 0.20,   # 20% Кэш/стейблы
    },
    
    # Ребалансировочные зоны (допуск)
    'bands': {
        'inner': 0.02,   # 2% — зона бездействия
        'outer': 0.05,   # 5% — триггер ребалансировки
        'critical': 0.10 # 10% — немедленная ребалансировка
    }
}

def check_rebalance_needed(current_allocations, target_allocations):
    """
    Определить, требуется ли ребалансировка портфеля.
    
    Использует ребалансировку на основе порогов с зонами.
    """
    deviations = {}
    actions = []
    
    for asset, target in target_allocations.items():
        current = current_allocations.get(asset, 0)
        deviation = current - target
        deviations[asset] = deviation
        
        # Проверка зон
        if abs(deviation) > REBALANCING_CONFIG['bands']['critical']:
            actions.append({
                'asset': asset,
                'action': 'immediate_rebalance',
                'deviation': deviation,
                'priority': 'critical'
            })
        elif abs(deviation) > REBALANCING_CONFIG['bands']['outer']:
            actions.append({
                'asset': asset,
                'action': 'schedule_rebalance',
                'deviation': deviation,
                'priority': 'normal'
            })
    
    return {'deviations': deviations, 'actions': actions}
```

### 4.4 Налогово-эффективные методы ребалансировки

```python
TAX_EFFICIENT_METHODS = {
    # 1. Ребалансировка денежными потоками (предпочтительно)
    'cash_flow': {
        'description': 'Использовать новые взносы для ребалансировки',
        'tax_impact': 'none',
        'implementation': 'Направить новый DCA в недовложенные активы'
    },
    
    # 2. Ребалансировка при выводе
    'withdrawal': {
        'description': 'Продавать из перекупленных активов при выводе',
        'tax_impact': 'minimal',
        'implementation': 'Приоритет продажи перекупленных позиций'
    },
    
    # 3. Налоговый харвестинг убытков
    'tax_loss_harvesting': {
        'description': 'Реализовать убытки для компенсации прибылей',
        'tax_impact': 'positive',
        'conditions': 'Актив имеет нереализованный убыток > $100',
        'wash_sale_rule': 'Избегать повторной покупки в течение 30 дней'
    },
    
    # 4. Выбор лотов
    'lot_selection': {
        'description': 'Выбирать конкретные налоговые лоты для минимизации прибыли',
        'methods': {
            'hifo': 'Сначала самая высокая стоимость — минимизирует прибыли',
            'fifo': 'Первый пришел первый ушел — по умолчанию',
            'lifo': 'Последний пришел первый ушел — недавние покупки'
        }
    }
}

def calculate_tax_efficient_rebalance(portfolio, target_allocations, tax_bracket=0.25):
    """
    Расчет сделок ребалансировки с минимизацией налогового воздействия.
    """
    rebalance_plan = []
    
    for asset, target_pct in target_allocations.items():
        current_value = portfolio.get_asset_value(asset)
        target_value = portfolio.total_value * target_pct
        diff = target_value - current_value
        
        if diff > 0:  # Нужно купить
            rebalance_plan.append({
                'asset': asset,
                'action': 'buy',
                'amount': diff,
                'tax_impact': 0
            })
        
        elif diff < 0:  # Нужно продать
            # Расчет оптимальных лотов для продажи
            lots = portfolio.get_tax_lots(asset)
            
            # Сортировка по себестоимости (HIFO)
            lots.sort(key=lambda x: x.cost_basis, reverse=True)
            
            amount_to_sell = abs(diff)
            lots_to_sell = []
            
            for lot in lots:
                if amount_to_sell <= 0:
                    break
                
                sell_amount = min(lot.quantity * lot.current_price, amount_to_sell)
                gain_loss = (lot.current_price - lot.cost_basis) * (sell_amount / lot.current_price)
                
                lots_to_sell.append({
                    'lot_id': lot.id,
                    'amount': sell_amount,
                    'gain_loss': gain_loss
                })
                amount_to_sell -= sell_amount
            
            total_gain = sum(l['gain_loss'] for l in lots_to_sell)
            tax_cost = max(0, total_gain) * tax_bracket
            
            rebalance_plan.append({
                'asset': asset,
                'action': 'sell',
                'amount': abs(diff),
                'lots': lots_to_sell,
                'estimated_gain': total_gain,
                'estimated_tax': tax_cost
            })
    
    return rebalance_plan
```

### 4.5 Логика распределения взносов

```python
class DCAAllocator:
    
    def __init__(self, target_allocations, volatility_adjustment=True):
        self.target_allocations = target_allocations
        self.volatility_adjustment = volatility_adjustment
    
    def allocate_contribution(self, contribution_amount, current_portfolio):
        """
        Распределение DCA-взноса между активами.
        
        Стратегии:
            1. Целевой взвешенный: Пропорционально целевому распределению
            2. Сначала недовложенный: Все в наиболее недовложенный актив
            3. Скорректированный по волатильности: Больше в высоковолатильные активы
        """
        allocations = {}
        
        # Расчет текущих весов
        total_value = current_portfolio.total_value
        current_weights = {
            asset: current_portfolio.get_value(asset) / total_value
            for asset in self.target_allocations.keys()
        }
        
        # Расчет отклонений от цели
        deviations = {
            asset: self.target_allocations[asset] - current_weights.get(asset, 0)
            for asset in self.target_allocations.keys()
        }
        
        # Стратегия: Сначала недовложенный с корректировкой по волатильности
        if self.volatility_adjustment:
            # Получить оценки волатильности (на основе ATR)
            volatilities = self.calculate_volatility_scores()
            
            # Расчет весов распределения
            weights = {}
            for asset in self.target_allocations.keys():
                # База на отклонении (недовложен = высокий приоритет)
                base_weight = max(0, deviations[asset])
                
                # Корректировка на волатильность (высокая вол = потенциально высокая доходность)
                vol_adjustment = 1 + (volatilities[asset] - 0.5) * 0.2
                
                weights[asset] = base_weight * vol_adjustment
            
            # Нормализация весов
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}
            else:
                # Если сбалансировано, использовать целевые веса
                weights = self.target_allocations
        
        else:
            # Простое целевое взвешивание
            weights = self.target_allocations
        
        # Расчет сумм в USD
        allocations = {
            asset: contribution_amount * weight
            for asset, weight in weights.items()
        }
        
        return allocations
    
    def calculate_volatility_scores(self):
        """
        Расчет нормализованных оценок волатильности (шкала 0-1).
        """
        atrs = {}
        for asset in self.target_allocations.keys():
            data = self.get_price_data(asset, days=30)
            atrs[asset] = calculate_atr(data, 14)
        
        # Нормализация к диапазону 0-1
        max_atr = max(atrs.values())
        min_atr = min(atrs.values())
        
        if max_atr == min_atr:
            return {asset: 0.5 for asset in atrs}
        
        return {
            asset: (atr - min_atr) / (max_atr - min_atr)
            for asset, atr in atrs.items()
        }
```

---

## 5. Тактическое/Кризисное развертывание

### 5.1 Обзор
Тактическое развертывание выделяет дополнительный капитал во время рыночных дислокаций на основе предопределенных индикаторов страха и уровней просадки.

### 5.2 Условия триггера

```python
CRISIS_TRIGGERS = {
    # Индекс Страха и Жадности
    'fear_greed_index': {
        'source': 'alternative.me',
        'update_frequency': 'daily',
        'triggers': {
            'extreme_fear': {'threshold': 20, 'multiplier': 2.0},
            'fear': {'threshold': 40, 'multiplier': 1.5},
            'neutral': {'threshold': 50, 'multiplier': 1.0},
            'greed': {'threshold': 75, 'multiplier': 0.5},
            'extreme_greed': {'threshold': 80, 'multiplier': 0.0}
        }
    },
    
    # Триггеры просадки (от ATH)
    'drawdown_triggers': {
        'btc_drawdown': {
            '10_pct': {'allocation': 0.10, 'aggression': 1.0},
            '20_pct': {'allocation': 0.15, 'aggression': 1.5},
            '30_pct': {'allocation': 0.20, 'aggression': 2.0},
            '40_pct': {'allocation': 0.25, 'aggression': 2.5},
            '50_pct': {'allocation': 0.30, 'aggression': 3.0}
        }
    },
    
    # VIX-стиль волатильности (BVOL для крипты)
    'volatility_spike': {
        'threshold_14d': 0.80,  # 80-й процентиль
        'threshold_30d': 0.90,  # 90-й процентиль
        'allocation_boost': 1.5
    },
    
    # Сигналы капитуляции
    'capitulation': {
        'sopr': {'threshold': 0.95, 'description': 'SOPR < 1 (продажа в убыток)'},
        'nupl': {'threshold': 0.0, 'description': 'NUPL отрицательный'},
        'mvrv': {'threshold': 1.0, 'description': 'MVRV < 1'},
        'allocation_boost': 2.0
    }
}
```

### 5.3 Правила размера развертывания

```python
class CrisisDeploymentManager:
    
    def __init__(self, base_monthly_allocation, max_deployment_pct=0.50):
        self.base_monthly = base_monthly_allocation
        self.max_deployment_pct = max_deployment_pct  # Макс 50% резерва
        self.deployed_this_crisis = 0
        self.deployment_history = []
    
    def calculate_deployment_size(self, crisis_signals, available_reserve):
        """
        Расчет размера развертывания на основе серьезности кризиса.
        
        Использует систему кумулятивного скоринга.
        """
        severity_score = 0
        multipliers = []
        
        # Вклад Страха и Жадности
        if 'fear_greed' in crisis_signals:
            fg = crisis_signals['fear_greed']
            if fg <= 20:
                severity_score += 3
                multipliers.append(2.0)
            elif fg <= 40:
                severity_score += 2
                multipliers.append(1.5)
        
        # Вклад просадки
        if 'drawdown_pct' in crisis_signals:
            dd = crisis_signals['drawdown_pct']
            if dd >= 50:
                severity_score += 3
                multipliers.append(3.0)
            elif dd >= 40:
                severity_score += 2
                multipliers.append(2.5)
            elif dd >= 30:
                severity_score += 1
                multipliers.append(2.0)
        
        # Вклад волатильности
        if 'volatility_percentile' in crisis_signals:
            vol = crisis_signals['volatility_percentile']
            if vol >= 0.90:
                severity_score += 2
                multipliers.append(1.5)
        
        # Сигналы капитуляции
        if 'capitulation_signals' in crisis_signals:
            cap_count = sum(crisis_signals['capitulation_signals'].values())
            severity_score += cap_count
            if cap_count >= 2:
                multipliers.append(2.0)
        
        # Расчет множителя развертывания
        avg_multiplier = sum(multipliers) / len(multipliers) if multipliers else 1.0
        
        # Пошаговое развертывание на основе серьезности
        if severity_score >= 7:
            deployment_pct = 0.30  # 30% резерва
        elif severity_score >= 5:
            deployment_pct = 0.20
        elif severity_score >= 3:
            deployment_pct = 0.10
        else:
            deployment_pct = 0.05
        
        # Применение множителя
        deployment_pct *= avg_multiplier
        
        # Ограничение максимумом
        deployment_pct = min(deployment_pct, self.max_deployment_pct)
        
        # Проверка лимита оставшегося резерва
        remaining_pct = 1 - (self.deployed_this_crisis / available_reserve)
        deployment_pct = min(deployment_pct, remaining_pct)
        
        deployment_amount = available_reserve * deployment_pct
        
        return {
            'amount': deployment_amount,
            'severity_score': severity_score,
            'multiplier': avg_multiplier,
            'deployment_pct': deployment_pct,
            'remaining_reserve': available_reserve - deployment_amount
        }
    
    def time_weighted_deployment(self, total_amount, days=30):
        """
        Развертывание во времени для избежания ловли падающего ножа.
        
        Реализует усреднение стоимости доллара в кризис.
        """
        daily_amount = total_amount / days
        
        schedule = []
        for day in range(days):
            # Ускорение развертывания если условия ухудшаются
            day_multiplier = 1 + (day / days) * 0.5  # До 1.5x в конце
            
            schedule.append({
                'day': day + 1,
                'base_amount': daily_amount,
                'adjusted_amount': daily_amount * day_multiplier,
                'cumulative': sum(s['adjusted_amount'] for s in schedule) + daily_amount * day_multiplier
            })
        
        return schedule
```

### 5.4 Условия выхода

```python
EXIT_TRIGGERS = {
    'profit_targets': {
        'tier_1': {'gain': 0.25, 'action': 'sell_25_pct'},
        'tier_2': {'gain': 0.50, 'action': 'sell_30_pct'},
        'tier_3': {'gain': 1.00, 'action': 'sell_25_pct'},
        'tier_4': {'gain': 2.00, 'action': 'sell_20_pct'},
        'runner': {'description': 'Удерживать остаток с трейлинг-стопом'}
    },
    
    'fear_greed_recovery': {
        'exit_start': 50,    # Нейтральный
        'full_exit': 75,     # Жадность
        'action': 'начать_фиксацию_прибыли'
    },
    
    'time_based': {
        'min_hold_days': 90,
        'max_hold_days': 365,
        'action_at_max': 'оценить_и_выйти'
    },
    
    'drawdown_recovery': {
        'exit_trigger': 'цена_в_пределах_10_pct_от_ath',
        'action': 'забрать_прибыли_вернуться_в_базу'
    },
    
    'emergency_exit': {
        'new_crisis': 'просадка_развернутого_капитала > 20%',
        'action': 'выход_по_стоп_лоссу'
    }
}
```

### 5.5 Логика возврата в базу

```python
class ReturnToBaseManager:
    
    def __init__(self, base_allocation, tactical_allocation):
        self.base = base_allocation
        self.tactical = tactical_allocation
        self.profits_taken = 0
    
    def evaluate_return_to_base(self, current_state):
        """
        Определить, должен ли тактический развертывание вернуться к базовой стратегии.
        """
        signals = []
        
        # 1. Достигнута цель прибыли
        unrealized_pnl = current_state['tactical_unrealized_pnl']
        if unrealized_pnl > 0.50:  # Прибыль 50%+
            signals.append({
                'signal': 'return_to_base',
                'priority': 'high',
                'reason': f'Цель прибыли превышена: {unrealized_pnl:.2%}'
            })
        
        # 2. Рыночный сентимент восстановился
        fear_greed = current_state['fear_greed_index']
        if fear_greed > 60:  # Территория жадности
            signals.append({
                'signal': 'begin_profit_taking',
                'priority': 'medium',
                'reason': f'Рыночный сентимент восстановился: {fear_greed}'
            })
        
        # 3. Просадка восстановилась
        drawdown = current_state['drawdown_from_ath']
        if drawdown < 0.10:  # В пределах 10% от ATH
            signals.append({
                'signal': 'return_to_base',
                'priority': 'medium',
                'reason': f'Просадка восстановилась: {drawdown:.2%}'
            })
        
        # 4. Временной лимит
        days_deployed = current_state['days_since_deployment']
        if days_deployed > 365:
            signals.append({
                'signal': 'mandatory_rebalance',
                'priority': 'high',
                'reason': f'Достигнут временной лимит: {days_deployed} дней'
            })
        
        return signals
    
    def execute_return_to_base(self, current_holdings, target_base_allocations):
        """
        Постепенный возврат тактического распределения к базовой стратегии.
        """
        rebalance_trades = []
        
        total_value = sum(current_holdings.values())
        
        for asset, target_pct in target_base_allocations.items():
            target_value = total_value * target_pct
            current_value = current_holdings.get(asset, 0)
            
            diff = target_value - current_value
            
            if abs(diff) > total_value * 0.01:  # Мин 1% для сделки
                rebalance_trades.append({
                    'asset': asset,
                    'action': 'buy' if diff > 0 else 'sell',
                    'amount': abs(diff),
                    'reason': 'return_to_base_allocation'
                })
        
        return rebalance_trades
```

### 5.6 Псевдокод развертывания в кризисе

```python
class CrisisDeploymentStrategy:
    
    def __init__(self, reserve_fund_pct=0.30):
        self.reserve_fund_pct = reserve_fund_pct
        self.deployment_active = False
        self.deployed_amount = 0
        self.base_strategy_allocation = 0.70  # 70% база, 30% резерв
    
    async def analyze(self, market_data):
        signals = []
        
        # Сбор индикаторов кризиса
        crisis_signals = {
            'fear_greed': await self.get_fear_greed_index(),
            'drawdown_pct': self.calculate_drawdown(market_data),
            'volatility_percentile': self.get_volatility_percentile(market_data),
            'capitulation_signals': self.check_onchain_capitulation()
        }
        
        # Проверка условий кризиса
        is_crisis = self.evaluate_crisis_conditions(crisis_signals)
        
        if is_crisis and not self.deployment_active:
            # Расчет развертывания
            available_reserve = self.portfolio.value * self.reserve_fund_pct
            
            deployment = self.calculate_deployment_size(
                crisis_signals, 
                available_reserve
            )
            
            # Создание графика развертывания
            schedule = self.time_weighted_deployment(
                deployment['amount'], 
                days=30
            )
            
            signals.append(CrisisDeploymentSignal(
                amount=deployment['amount'],
                schedule=schedule,
                severity=deployment['severity_score']
            ))
            
            self.deployment_active = True
            self.deployed_amount = deployment['amount']
        
        elif self.deployment_active:
            # Проверка условий выхода
            exit_signals = self.evaluate_exit_conditions(market_data, crisis_signals)
            
            if exit_signals:
                for signal in exit_signals:
                    if signal['type'] == 'profit_taking':
                        signals.append(PartialExitSignal(
                            pct=signal['pct'],
                            reason=signal['reason']
                        ))
                    elif signal['type'] == 'return_to_base':
                        signals.append(ReturnToBaseSignal())
                        self.deployment_active = False
        
        return signals
    
    def evaluate_crisis_conditions(self, signals):
        """Определить, выполнены ли критерии развертывания в кризисе."""
        score = 0
        
        if signals['fear_greed'] <= 25:
            score += 2
        elif signals['fear_greed'] <= 40:
            score += 1
        
        if signals['drawdown_pct'] >= 0.30:
            score += 2
        elif signals['drawdown_pct'] >= 0.20:
            score += 1
        
        if any(signals['capitulation_signals'].values()):
            score += 1
        
        return score >= 3  # Развернуть если score >= 3
```

---

## 6. Фреймворк управления рисками

### 6.1 Универсальные лимиты риска

```yaml
HARD_LIMITS:
    max_position_size: 5%          # На позицию
    max_sector_exposure: 15%       # На коррелированную группу
    max_daily_loss: 2%             # Остановить торговлю
    max_weekly_loss: 5%            # Аварийная остановка
    max_drawdown: 15%              # Прерыватель
    max_leverage: 1.0              # Только спот (без маржи)

POSITION_RISK:
    stop_loss_atr_multiplier: 2.0
    take_profit_risk_reward: 2.0
    max_risk_per_trade: 1.0%

CORRELATION_LIMITS:
    max_correlated_positions: 3
    correlation_threshold: 0.70
    correlation_lookback: 30_days
```

### 6.2 Матрица размеров позиций

| Тип стратегии | Базовый риск | Макс размер | Множитель уверенности |
|--------------|--------------|-------------|----------------------|
| Следование за трендом | 1.0% | 5% | 0.5x - 1.0x |
| Арбитраж финансирования | 0.5% | 10% | Фиксированный |
| Сеточная торговля | 0.5% на уровень | 50% общий | Фиксированный |
| DCA | 1.0% на покупку | 20% недельный | Фиксированный |
| Кризисное развертывание | 2.0% | 30% резерв | Динамический |

### 6.3 Иерархия стоп-лоссов

```python
STOP_LOSS_HIERARCHY = {
    # Уровень 1: Стоп стратегии (самый тесный)
    'strategy_stop': {
        'trigger': 'специфический сигнал стратегии',
        'execution': 'immediate_market_order',
        'priority': 1
    },
    
    # Уровень 2: Технический стоп
    'technical_stop': {
        'trigger': 'ATR_based или пробой поддержки',
        'distance': '2x ATR',
        'execution': 'stop_limit_order',
        'priority': 2
    },
    
    # Уровень 3: Стоп портфеля (аварийный)
    'portfolio_stop': {
        'trigger': 'daily_loss_limit OR drawdown_limit',
        'execution': 'close_all_positions',
        'priority': 3
    }
}
```

---

## 7. Справочник по реализации

### 7.1 Структура класса стратегии

```python
from abc import ABC, abstractmethod
from typing import List, Dict
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class Signal:
    symbol: str
    side: str  # 'buy', 'sell', 'close'
    size: Decimal
    price: Decimal
    stop_loss: Decimal = None
    take_profit: Decimal = None
    metadata: Dict = None

class BaseStrategy(ABC):
    """Базовый класс для всех торговых стратегий."""
    
    def __init__(self, name: str, symbols: List[str], params: Dict):
        self.name = name
        self.symbols = symbols
        self.params = params
        self.is_active = True
        self.positions = {}
    
    @abstractmethod
    def analyze(self, market_data: Dict) -> List[Signal]:
        """Генерация торговых сигналов из рыночных данных."""
        pass
    
    @abstractmethod
    def on_fill(self, symbol: str, side: str, price: Decimal, size: Decimal):
        """Обработка событий исполнения ордеров."""
        pass
    
    def calculate_position_size(
        self, 
        portfolio_value: Decimal,
        entry_price: Decimal,
        stop_price: Decimal,
        risk_pct: float = 0.01
    ) -> Decimal:
        """Расчет размера позиции на основе риска."""
        risk_amount = portfolio_value * Decimal(str(risk_pct))
        stop_distance = abs(entry_price - stop_price)
        
        if stop_distance == 0:
            return Decimal('0')
        
        quantity = risk_amount / stop_distance
        return quantity
    
    def calculate_atr(self, highs, lows, closes, period=14):
        """Расчет Average True Range."""
        tr1 = [h - l for h, l in zip(highs, lows)]
        tr2 = [abs(h - c) for h, c in zip(highs[1:], closes[:-1])]
        tr3 = [abs(l - c) for l, c in zip(lows[1:], closes[:-1])]
        
        tr = [max(t1, t2, t3) for t1, t2, t3 in zip(tr1[1:], tr2, tr3)]
        
        # Сглаживание Уайлдера
        atr = [sum(tr[:period]) / period]
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        
        return atr[-1] if atr else 0
```

### 7.2 Схема конфигурации

```yaml
# config/strategies.yaml
strategies:
  trend_following:
    enabled: true
    symbols: ['BTCUSDT', 'ETHUSDT']
    timeframes: ['1h', '4h']
    indicators:
      ema_fast: {period: 9, type: 'ema'}
      ema_slow: {period: 21, type: 'ema'}
      atr: {period: 14}
      adx: {period: 14}
    entry:
      ema_cross: true
      adx_min: 25
      volume_confirm: 1.2
    risk:
      stop_atr_mult: 2.0
      risk_per_trade: 0.01
      max_position: 0.05

  funding_arbitrage:
    enabled: false
    min_annualized_rate: 0.10
    max_basis_pct: 0.005
    rebalance_threshold: 0.02
    exchanges: ['bybit', 'binance']

  grid_trading:
    enabled: true
    grid_levels: 10
    spacing_pct: 1.0
    range_pct: 20.0
    max_investment_pct: 50.0
    reset_on_breakout: true

  dca:
    enabled: true
    interval_hours: 24
    amount_usdt: 100
    volatility_adjust: true
    targets:
      BTC: 0.50
      ETH: 0.30
      USDT: 0.20

  crisis_deployment:
    enabled: false
    reserve_pct: 0.30
    triggers:
      fear_greed_threshold: 25
      drawdown_threshold: 0.30
    deployment_schedule_days: 30
```

### 7.3 Дашборд ключевых метрик

```python
METRICS_TO_TRACK = {
    # Производительность
    'total_return': 'cumulative_pnl / starting_capital',
    'sharpe_ratio': 'excess_return / volatility',
    'sortino_ratio': 'excess_return / downside_volatility',
    'max_drawdown': 'peak_to_trough_decline',
    'calmar_ratio': 'annual_return / max_drawdown',
    
    # Метрики сделок
    'win_rate': 'winning_trades / total_trades',
    'profit_factor': 'gross_profit / gross_loss',
    'avg_win_loss_ratio': 'avg_win / avg_loss',
    'expectancy': '(win_rate * avg_win) - (loss_rate * avg_loss)',
    
    # Метрики риска
    'var_95': '5th percentile of returns',
    'cvar_95': 'average of worst 5% returns',
    'beta': 'correlation_to_benchmark',
    'correlation_matrix': 'inter-asset_correlations',
    
    # Операционные
    'uptime_pct': 'strategy_execution_time / total_time',
    'slippage_avg': 'expected_vs_actual_fill_difference',
    'fill_rate': 'filled_orders / total_orders'
}
```

---

## Приложение: Справочник формул

### Технические индикаторы

```
EMA:    EMA_today = Price_today × k + EMA_yesterday × (1 - k)
        where k = 2 / (N + 1)

ATR:    TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        ATR = SMA(TR, N)  [или сглаживание Уайлдера]

ADX:    +DM = High_today - High_yesterday (if positive, else 0)
        -DM = Low_yesterday - Low_today (if positive, else 0)
        +DI = 100 × SMA(+DM, N) / ATR
        -DI = 100 × SMA(-DM, N) / ATR
        DX = 100 × |+DI - -DI| / (+DI + -DI)
        ADX = SMA(DX, N)

RSI:    RS = SMA(Gains, N) / SMA(Losses, N)
        RSI = 100 - (100 / (1 + RS))

Полосы Боллинджера:
        Middle = SMA(Close, 20)
        Upper = Middle + (2 × StdDev)
        Lower = Middle - (2 × StdDev)
```

### Формулы риска

```
Размер позиции (Фиксированная фракция):
        Q = (Capital × Risk%) / (Entry - Stop)

Критерий Келли:
        f* = (p × b - q) / b
        where p = вероятность победы, q = вероятность поражения, b = отношение выигрыша/проигрыша

Коэффициент Шарпа:
        S = (Rp - Rf) / σp

Максимальная просадка:
        MDD = max[(Peak - Trough) / Peak]
```

---

*Версия документа: 1.0*  
*Последнее обновление: 2026-02-13*  
*Предназначение: Руководство по реализации для разработчиков*
