//! Frame pacing.
//!
//! **A deliberate divergence from the agent, stated as such.** The decoded
//! pacing reads only `GetSystemTime`'s `wMilliseconds`, so its own elapsed
//! measurement wraps every second and cannot tell a 1.2-second stall from a
//! 200 ms one. The Python reference reproduces that faithfully in
//! `pacing_sleep_ms`, including the wrap; a host has no reason to inherit it.
//! [`crate::stream::frame_interval_ms`] still supplies the target, so the
//! interval and its truncation are the decoded ones.

use crate::stream::frame_interval_ms;
use crate::Result;

/// Paces the outbound frame loop to a target rate.
///
/// The clock is a parameter rather than a call to the system clock, which is
/// what lets the conformance harness drive this implementation and the other
/// two through the same instants and compare the schedule.
pub struct Pacer {
    interval_s: f64,
    next: f64,
    scheduled: bool,
}

impl Pacer {
    pub fn new(fps: i32) -> Result<Self> {
        Ok(Self {
            interval_s: frame_interval_ms(fps)? as f64 / 1000.0,
            next: 0.0,
            scheduled: false,
        })
    }

    pub fn interval_s(&self) -> f64 {
        self.interval_s
    }

    /// Seconds to wait before the next frame, given the current time. Never
    /// negative.
    ///
    /// Schedules against the previous *target* rather than the previous
    /// wakeup, so a late frame does not push every later frame late. A stall
    /// longer than one interval resets the schedule instead of catching up in
    /// a burst — on a display, a burst of backlogged frames is worse than the
    /// frames simply having been missed.
    pub fn sleep_s(&mut self, now: f64) -> f64 {
        if !self.scheduled {
            self.next = now + self.interval_s;
            self.scheduled = true;
            return 0.0;
        }
        let wait = self.next - now;
        if wait <= 0.0 {
            self.next = now + self.interval_s;
            return 0.0;
        }
        self.next += self.interval_s;
        wait
    }
}
