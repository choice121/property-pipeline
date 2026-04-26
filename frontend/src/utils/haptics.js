// Lightweight haptic feedback wrappers.
// Falls through silently on devices that don't support the Vibration API.
export function tapHaptic() {
  if (navigator.vibrate) navigator.vibrate(8)
}
export function selectHaptic() {
  if (navigator.vibrate) navigator.vibrate(12)
}
export function successHaptic() {
  if (navigator.vibrate) navigator.vibrate([10, 30, 10])
}
export function warningHaptic() {
  if (navigator.vibrate) navigator.vibrate([20, 60, 20])
}
