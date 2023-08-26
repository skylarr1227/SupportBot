require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const path = require('path');
const passport = require('passport');
const DiscordStrategy = require('passport-discord').Strategy;
const app = express();
const port = 3000;


// Configure PostgreSQL connection
const pool = new Pool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
});

passport.serializeUser((user, done) => done(null, user));
passport.deserializeUser((obj, done) => done(null, obj));

app.use(require('express-session')({ secret: 'secret_key', resave: false, saveUninitialized: false }));
app.use(passport.initialize());
app.use(passport.session());

passport.use(new DiscordStrategy({
    clientID: process.env.DISCORD_CLIENT_ID,
    clientSecret: process.env.DISCORD_CLIENT_SECRET,
    callbackURL: 'http://localhost:3000/auth/discord/callback',
    scope: ['identify'] // Include the 'identify' scope
  }, (accessToken, refreshToken, profile, done) => {
    if (allowedUserIDs.includes(profile.id)) {
      return done(null, profile);
    } else {
      return done(null, false, { message: 'Not authorized' });
    }
  }));
function serveAuthenticatedStatic(req, res, next) {
    // Allow authentication-related paths to bypass authentication
    if (req.path.startsWith('/auth/discord')) {
      return next();
    }
  
    if (req.isAuthenticated()) {
      return express.static(path.join(__dirname, 'public'))(req, res, next);
    } else {
      res.redirect('/auth/discord'); // Redirect to Discord authentication if not authenticated
    }
  }
  
app.use(serveAuthenticatedStatic);

// Enable JSON body parsing
app.use(express.json());

// Middleware to check if the user is authenticated
function isAuthenticated(req, res, next) {
    if (req.isAuthenticated()) {
      return next();
    }
    res.redirect('/auth/discord'); // Redirect to Discord authentication if not authenticated
  }
  
// Whitelist of allowed Discord user IDs
const allowedUserIDs = ['790722073248661525', '394270361983778816'];





app.get('/auth/discord', passport.authenticate('discord'));

app.get('/auth/discord/callback',
    passport.authenticate('discord', { failureRedirect: '/unauthorized' }),
    (req, res) => res.redirect('/'));


// Endpoint to get all contests
app.get('/contests', isAuthenticated, async (req, res) => {
    try {
      const result = await pool.query('SELECT * FROM Contests');
      res.json(result.rows);
    } catch (error) {
      console.error(error);
      res.status(500).json({ error: 'An error occurred' });
    }
  });

app.get('/unauthorized', (req, res) => res.send('You are not authorized to view this content.'));


app.put('/contests/:id', async (req, res) => {
    try {
      const { id } = req.params;
      const { week, monday, tuesday, wednesday, thursday, friday, saturday, sunday } = req.body;
      const query = `UPDATE Contests SET week = $1, monday = $2, tuesday = $3, wednesday = $4, thursday = $5, friday = $6, saturday = $7, sunday = $8 WHERE id = $9`;
      const values = [week, monday, tuesday, wednesday, thursday, friday, saturday, sunday, id];
      const result = await pool.query(query, values);
      res.json(result.rows);
    } catch (error) {
      console.error(error);
      res.status(500).json({ error: 'An error occurred' });
    }
  });

// Additional endpoints for updating, deleting, etc.

// Start the server
app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
