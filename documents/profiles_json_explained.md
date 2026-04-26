# Cold Chain Monitor - Configuration Profiles

## Overview

The `config/profiles.json` file defines temperature and humidity thresholds for different types of products stored in a cold chain monitoring system. Each product category has specific environmental requirements that must be maintained to ensure product quality and safety.

## Purpose

This configuration file allows the system to:

- **Monitor conditions**: Continuously check if stored products remain within acceptable ranges
- **Trigger alerts**: Generate warnings when temperature or humidity exceeds thresholds
- **Ensure compliance**: Help maintain regulatory standards for sensitive products
- **Prevent spoilage**: Avoid financial losses from improper storage conditions

## File Structure

The file is organized as a JSON object with four main product profiles:

```json
{
  "profile_name": {
    "temp_min": number,
    "temp_max": number,
    "humidity_max": number
  }
}
```

### Field Descriptions

| Field | Type | Description | Unit |
|-------|------|-------------|------|
| `temp_min` | number | Minimum acceptable temperature | °C (Celsius) |
| `temp_max` | number | Maximum acceptable temperature | °C (Celsius) |
| `humidity_max` | number | Maximum acceptable relative humidity | % (percentage) |

## Product Profiles Explained

### 1. Standard Vaccines

```json
{
  "standard_vaccines": {
    "temp_min": 2.0,
    "temp_max": 8.0,
    "humidity_max": 80
  }
}
```

**Description**: Vaccines require strict temperature control to maintain efficacy. The "cold chain" for vaccines is typically maintained between 2-8°C.

**Temperature Range**: 2°C to 8°C (Cold but not frozen)

**Why this range?**
- Below 2°C: Some vaccines can freeze, causing irreversible damage to their proteins
- Above 8°C: Accelerated degradation, reduced potency, potential spoilage

**Humidity**: Must stay below 80% to prevent condensation and moisture damage to packaging.

**Example**:
- ✅ Acceptable: 5°C temperature, 65% humidity
- ❌ Too cold: 0°C (risk of freezing)
- ❌ Too warm: 10°C (vaccine degradation)
- ❌ Too humid: 85% humidity (packaging damage)

---

### 2. Fresh Produce

```json
{
  "fresh_produce": {
    "temp_min": 1.0,
    "temp_max": 6.0,
    "humidity_max": 90
  }
}
```

**Description**: Fresh fruits, vegetables, and other perishable produce need cool temperatures with high humidity to prevent wilting while avoiding freezing.

**Temperature Range**: 1°C to 6°C (Refrigerated, above freezing)

**Why this range?**
- Below 1°C: Many fruits and vegetables can suffer chilling injury or freeze
- Above 6°C: Accelerated ripening, bacterial growth, reduced shelf life

**Humidity**: Higher tolerance (up to 90%) to prevent dehydration and preserve freshness.

**Example**:
- ✅ Acceptable: 3°C temperature, 85% humidity
- ❌ Too cold: -1°C (freezing causes cell damage)
- ❌ Too warm: 8°C (rapid spoilage)
- ❌ Too dry: 70% humidity (produce wilts)

---

### 3. Frozen Foods

```json
{
  "frozen_foods": {
    "temp_min": -25.0,
    "temp_max": -15.0,
    "humidity_max": 60
  }
}
```

**Description**: Frozen products like ice cream, frozen meats, and vegetables must remain deeply frozen to prevent thawing and refreezing.

**Temperature Range**: -25°C to -15°C (Deep frozen)

**Why this range?**
- Above -15°C: Risk of partial thawing, which causes texture degradation and bacterial growth
- Below -25°C: Unnecessary energy consumption without significant benefit

**Humidity**: Lower tolerance (60%) because ice formation is a concern in humid freezers.

**Example**:
- ✅ Acceptable: -20°C temperature, 50% humidity
- ❌ Too warm: -10°C (ice cream becomes soft, refreezing causes crystals)
- ❌ Not frozen enough: -12°C (meat develops freezer burn)

---

### 4. Pharmaceuticals

```json
{
  "pharmaceuticals": {
    "temp_min": 15.0,
    "temp_max": 25.0,
    "humidity_max": 60
  }
}
```

**Description**: Many medicines, especially tablets, capsules, and some injectables, require controlled room temperature storage.

**Temperature Range**: 15°C to 25°C (Room temperature)

**Why this range?**
- Below 15°C: Some medications may become less effective or unstable
- Above 25°C: Accelerated chemical degradation, reduced shelf life

**Humidity**: Must stay below 60% to prevent moisture absorption that can compromise pill integrity and effectiveness.

**Example**:
- ✅ Acceptable: 22°C temperature, 55% humidity
- ❌ Too cold: 10°C (some medicines crystallize or separate)
- ❌ Too hot: 30°C (medication breaks down faster)
- ❌ Too humid: 75% humidity (pills may dissolve or grow mold)

---

## Visual Range Diagrams

### Temperature Ranges Comparison

```
Temperature Scale (°C)
-30  -25  -20  -15  -10   -5    0    5    10   15   20   25   30
|          |          |          |          |          |
          [Frozen Foods: -25 to -15]
                                   [Vaccines: 2 to 8]
                                            [Fresh Produce: 1 to 6]
                                                             [Pharma: 15 to 25]
```

### Humidity Requirements Comparison

```
Humidity Scale (%)
0    10   20   30   40   50   60   70   80   90   100
|           |           |           |           |           |
           [Frozen/Pharma: max 60]
                               [Vaccines: max 80]
                                           [Fresh Produce: max 90]
```

## How the System Uses This File

1. **Real-time Monitoring**: IoT sensors in storage facilities continuously measure temperature and humidity
2. **Comparison**: Current readings are compared against the active profile's thresholds
3. **Alert Generation**: When values exceed limits:
   - Warnings appear on monitoring dashboards
   - SMS/email notifications may be sent to staff
   - Dashboard shows which specific threshold was breached
4. **Profile Selection**: Users select the appropriate profile based on what products are being stored

## Example Scenarios

### Scenario 1: Vaccine Storage Unit
```
Active Profile: standard_vaccines
Current: temp=7.5°C, humidity=78%
Status: ✅ Within range

Current: temp=0.5°C, humidity=79%
Status: ❌ ALERT - Temperature too low (below 2°C minimum)
```

### Scenario 2: Tropical Fruit Storage
```
Active Profile: fresh_produce
Current: temp=4°C, humidity=92%
Status: ❌ ALERT - Humidity too high (above 90% maximum)

Current: temp=2°C, humidity=88%
Status: ✅ Within range
```

### Scenario 3: Medicine Cabinet
```
Active Profile: pharmaceuticals
Current: temp=23°C, humidity=58%
Status: ✅ Within range

Current: temp=28°C, humidity=62%
Status: ❌ DUAL ALERT - Both temperature and humidity exceed limits
```

## Best Practices

1. **Profile Selection**: Choose the most restrictive profile when storing mixed products
2. **Regular Validation**: Schedule periodic checks of sensor calibration
3. **Emergency Response**: Have protocols ready for when alerts trigger
4. **Documentation**: Keep records of all alert events for compliance audits

## Related Files

- `config/settings.json` - System-wide configuration
- `src/controllers/monitoring.js` - Logic that reads these thresholds
- `src/models/alert.js` - Alert generation based on profile violations
