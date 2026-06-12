/**
 * Side-effect module that pins the process timezone to America/New_York.
 *
 * Must be the FIRST import of any test file that asserts on local-time
 * behavior (e.g. DST handling in streak calculations), so it runs before
 * date-fns or the module under test ever touches local time.
 */
process.env.TZ = 'America/New_York';
