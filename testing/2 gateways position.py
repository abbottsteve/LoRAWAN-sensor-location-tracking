# Two gateways Triangulation

'''
# RSSI Proximity (Received Signal Strength Indicator):
# The RSSI value can be used to estimate the distance between the device and the gateways.
# A stronger signal (higher RSSI) indicates closer proximity, while a weaker signal (lower RSSI) suggests greater distance.

# Differential RSSI:
# By comparing the RSSI values from multiple gateways, we can determine the device's position more accurately.
# For example, if Gateway A has a much stronger signal than Gateway B, the device is likely closer to Gateway A.

# TDoA Hyperbola (Time Difference of Arrival):
# If the gateways are synchronized, we can use the time difference of arrival (TDoA) of the signal at each gateway to calculate hyperbolas on which the device must lie.
'''
'''
Combining these methods is a common technique known as Hybrid Positioning or Sensor Fusion, and it significantly shrinks the "area of uncertainty" when you're limited to only two gateways.
When you combine these three, you are essentially performing a Constrained Optimization. Here is how they stack up:

1. The TDoA "Anchor"
The TDoA Hyperbola is your most mathematically "stiff" data point. It tells you exactly how much closer the device is to Gateway A than Gateway B. However, a hyperbola stretches out to infinity in both directions.
2. The RSSI "Boundary"
RSSI Proximity acts as a filter. If Gateway A sees a signal at -110 dBm, you know the device cannot be 10 miles away. By applying a Path Loss Model (like Log-Distance), you create a maximum radius.
The Result: This "chops off" the ends of the TDoA hyperbola, leaving you with a specific arc segment instead of an infinite line.
3. The Differential RSSI "Weight"
Differential RSSI looks at the ratio between the two signals. If Gateway A is much stronger than Gateway B, the probability shifts toward the Gateway A side of the hyperbola.
The Result: This allows the algorithm to apply a probability distribution (often visualized as a heat map) over the arc segment, highlighting the most likely "hot spot."
'''
'''
The "Map Matching" Secret Ingredient
In a 2-gateway scenario, developers often add one more layer: Topographic Constraints.
Since you know the sensor is likely on an arc, you can overlay that arc onto a map.
If the arc passes through a lake, a cliff, or a restricted building where your sensors shouldn't be, the algorithm ignores those points.
If the arc intersects a known road or hallway, you can snap the location to that coordinate with surprisingly high confidence.
'''
'''
Challenges to Keep in Mind
While combining them helps, you still face two major "physics" hurdles:
Multipath Interference: In cities, signals bounce off buildings. This can make a sensor look "further away" (weaker RSSI) or "delayed" (wrong TDoA), which can confuse the hybrid model.
Clock Synchronization: TDoA requires the two gateways to be perfectly synced (usually via GPS). If their clocks drift even by a few microseconds, your hyperbola could shift by hundreds of meters.
'''


# Approach:
# The Custom Hybrid Logic (The "Solver")

'''
The Data ObjectTTS will send a rx_metadata array in the uplink message. You need these fields:
- gateway_ids: To know the $(x, y)$ of Gateway A and B.
- rssi: For the Proximity/Differential calculation.
- fine_timestamp: For the TDoA hyperbola.

The Algorithm (High Level)
To combine them in code, you would typically use a Kalman Filter or a Particle Filter:

1. Define the Search Space: Create a grid of possible coordinates around the gateways.
2. TDoA Probability: For each point in the grid, calculate what the time difference should be and compare it to the actual fine_timestamp difference. Assign a probability score.
3. RSSI Probability: Use the Log-Distance Path Loss Model to calculate the probability of the device being at that grid point based on the RSSI.
   $$P(d) = P(d_0) - 10n \log_{10}\left(\frac{d}{d_0}\right)$$
4. Multiply Probabilities: Multiply the TDoA score by the RSSI score for every point. The point with the highest combined score is your location.
'''

