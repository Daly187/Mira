/**
 * Mira WhatsApp Bridge — Express HTTP server wrapping whatsapp-web.js.
 *
 * Runs on port 3001 (configurable via WA_PORT env var).
 * The Python agent calls this via HTTP to send/read WhatsApp messages.
 *
 * Auth: WhatsApp Web QR code scan (one-time, session persists).
 */

const express = require('express')
const cors = require('cors')
const { Client, LocalAuth } = require('whatsapp-web.js')
const qrcode = require('qrcode')
const qrcodeTerminal = require('qrcode-terminal')
const path = require('path')

const app = express()
app.use(cors())
app.use(express.json())

const PORT = process.env.WA_PORT || 3001
const SESSION_PATH = process.env.WA_SESSION_PATH || path.join(__dirname, '..', 'data', 'whatsapp-session')

// ── State ──────────────────────────────────────────────────
let currentQR = null
let connectionStatus = 'disconnected' // disconnected | qr_pending | connected | auth_failure
let clientReady = false

// ── WhatsApp Client ────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  },
})

client.on('qr', async (qr) => {
  connectionStatus = 'qr_pending'
  // Generate base64 QR for API consumers
  try {
    currentQR = await qrcode.toDataURL(qr)
  } catch (e) {
    console.error('QR generation failed:', e.message)
    currentQR = null
  }
  // Also print to terminal for local dev
  qrcodeTerminal.generate(qr, { small: true })
  console.log('[WA] QR code generated — scan with WhatsApp to authenticate')
})

client.on('ready', () => {
  connectionStatus = 'connected'
  clientReady = true
  currentQR = null
  console.log('[WA] WhatsApp Web client ready')
})

client.on('authenticated', () => {
  console.log('[WA] Session authenticated')
  currentQR = null
})

client.on('auth_failure', (msg) => {
  connectionStatus = 'auth_failure'
  clientReady = false
  console.error('[WA] Authentication failure:', msg)
})

client.on('disconnected', (reason) => {
  connectionStatus = 'disconnected'
  clientReady = false
  console.log('[WA] Disconnected:', reason)
  // Attempt reconnection after a delay
  setTimeout(() => {
    console.log('[WA] Attempting reconnection...')
    client.initialize().catch(e => console.error('[WA] Reconnect failed:', e.message))
  }, 10000)
})

// ── API Routes ─────────────────────────────────────────────

// GET /status — connection status + QR code state
app.get('/status', (req, res) => {
  res.json({
    status: connectionStatus,
    ready: clientReady,
    hasQR: !!currentQR,
  })
})

// GET /qr — returns current QR code as base64 data URL
app.get('/qr', (req, res) => {
  if (!currentQR) {
    return res.json({ qr: null, message: connectionStatus === 'connected' ? 'Already authenticated' : 'No QR available' })
  }
  res.json({ qr: currentQR })
})

// POST /send — send message: {phone: "+63...", text: "..."}
app.post('/send', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: 'WhatsApp not connected' })
  }

  const { phone, text } = req.body
  if (!phone || !text) {
    return res.status(400).json({ error: 'phone and text are required' })
  }

  try {
    // Convert phone to WhatsApp JID format (number@c.us)
    const jid = normalizePhone(phone) + '@c.us'
    const msg = await client.sendMessage(jid, text)
    console.log(`[WA] Sent to ${phone}: ${text.substring(0, 80)}...`)

    res.json({
      success: true,
      message_id: msg.id._serialized,
      timestamp: msg.timestamp,
    })
  } catch (e) {
    console.error(`[WA] Send failed to ${phone}:`, e.message)
    res.status(500).json({ error: e.message })
  }
})

// GET /messages/:phone?limit=20 — get recent messages from a chat
app.get('/messages/:phone', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: 'WhatsApp not connected' })
  }

  const phone = req.params.phone
  const limit = parseInt(req.query.limit) || 20

  try {
    const jid = normalizePhone(phone) + '@c.us'
    const chat = await client.getChatById(jid)
    const messages = await chat.fetchMessages({ limit })

    const result = messages
      .filter(m => m.body) // skip media-only
      .map(m => ({
        id: m.id._serialized,
        role: m.fromMe ? 'assistant' : 'user',
        content: m.body,
        timestamp: new Date(m.timestamp * 1000).toISOString(),
      }))

    res.json(result)
  } catch (e) {
    console.error(`[WA] Fetch messages failed for ${phone}:`, e.message)
    res.status(500).json({ error: e.message })
  }
})

// GET /unread — list chats with unread messages
app.get('/unread', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: 'WhatsApp not connected' })
  }

  try {
    const chats = await client.getChats()
    const unread = chats
      .filter(c => c.unreadCount > 0 && !c.isGroup)
      .map(c => ({
        name: c.name || 'Unknown',
        phone: c.id.user,
        unread_count: c.unreadCount,
        last_message: c.lastMessage ? c.lastMessage.body : '',
      }))

    res.json(unread)
  } catch (e) {
    console.error('[WA] Unread fetch failed:', e.message)
    res.status(500).json({ error: e.message })
  }
})

// POST /read/:phone — mark chat as read
app.post('/read/:phone', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: 'WhatsApp not connected' })
  }

  try {
    const jid = normalizePhone(req.params.phone) + '@c.us'
    const chat = await client.getChatById(jid)
    await chat.sendSeen()
    res.json({ success: true })
  } catch (e) {
    console.error(`[WA] Mark read failed:`, e.message)
    res.status(500).json({ error: e.message })
  }
})

// GET /contacts — list all WhatsApp contacts with names + numbers
app.get('/contacts', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: 'WhatsApp not connected' })
  }

  try {
    const contacts = await client.getContacts()
    const result = contacts
      .filter(c => c.isUser && !c.isMe && c.id.user)
      .map(c => ({
        name: c.name || c.pushname || 'Unknown',
        phone: c.id.user,
        jid: c.id._serialized,
        pushname: c.pushname || '',
      }))

    res.json(result)
  } catch (e) {
    console.error('[WA] Contacts fetch failed:', e.message)
    res.status(500).json({ error: e.message })
  }
})

// ── Helpers ────────────────────────────────────────────────

function normalizePhone(phone) {
  // Strip everything except digits
  return phone.replace(/[^0-9]/g, '')
}

// ── Start ──────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`[WA] WhatsApp bridge server listening on port ${PORT}`)
  console.log('[WA] Initializing WhatsApp Web client...')
  client.initialize().catch(e => {
    console.error('[WA] Client initialization failed:', e.message)
    connectionStatus = 'auth_failure'
  })
})
