# ZEBRAS Admin UI Guide

## Overview

The ZEBRAS Admin UI has been completely redesigned with a modern, intuitive interface. Access it at **http://localhost:43117** when running in HTTP mode.

## Features

### 🎨 Modern Design
- **Dark theme** with professional color scheme
- **Responsive layout** that works on all screen sizes
- **Smooth animations** and transitions
- **Toast notifications** for user feedback
- **Icon system** with Lucide icons for better visual communication

### 📊 Dashboard (`/`)
- Real-time statistics on autoresponder rules
- System health monitoring
- Quick action buttons to navigate to key features
- Recent activity feed (placeholder for future implementation)

### 💬 Auto Responder (`/autoresponder`)
- **Inline editing**: Click to edit rules directly in the table
- **Scope filtering**: Switch between GLOBAL and channel-specific rules
- **Search functionality**: Find rules by phrase or response text
- **Toggle enable/disable**: Quick toggle without page reload
- **Modal-based creation**: Clean, focused form for adding new rules
- **Live feedback**: Instant success/error messages via toasts

#### Features:
- Add rules with pattern matching (contains, exact, regex)
- Set rules as global or channel-specific
- Enable/disable rules with one click
- Delete rules with confirmation
- Case-sensitive matching option

### 🛡️ Channel Rules (`/rules`)
- **Channel selector**: Search and select channels from sidebar
- **Visual indicators**: See which channels have custom rules
- **Live preview**: See what will be blocked before saving
- **Toggle switches**: Modern UI for rule configuration
- **Auto-save feedback**: Immediate confirmation when rules are saved

#### Features:
- Configure bot message permissions
- Control top-level posts
- Manage thread reply permissions
- Reset to defaults option
- Visual preview of blocked content

### 👤 Invite Helper (`/invite`)
- **Channel selection**: Easy dropdown to configure admin and audit channels
- **Toggle notifications**: Simple switch for join notifications
- **DM message preview**: See how your welcome message will look
- **Clean form layout**: Organized, intuitive configuration

#### Features:
- Set admin channel for invite requests
- Configure audit channel for activity logs
- Toggle join notifications
- Customize welcome DM message
- Preview message before saving

## Technical Stack

### Frontend
- **Single Page Application (SPA)** - Pure static HTML with client-side routing
- **Tailwind CSS** - Utility-first CSS framework (loaded from CDN)
- **Alpine.js** - Lightweight JavaScript framework for reactivity (loaded from CDN)
- **Lucide Icons** - Beautiful, consistent icon set (loaded from CDN)
- **No build process** - Everything is served as static files

### Backend
- **FastAPI** - High-performance Python web framework
- **RESTful API** - JSON API endpoints at `/api/v1/*`
- **Async/await** - Non-blocking database operations

## API Endpoints

### Auto Responder
- `GET /api/v1/autoresponder/rules` - List all rules
- `POST /api/v1/autoresponder/rules` - Create new rule
- `PATCH /api/v1/autoresponder/rules/{id}` - Update rule
- `DELETE /api/v1/autoresponder/rules/{id}` - Delete rule

### Channel Rules
- `GET /api/v1/rules/{channel_id}` - Get channel rules
- `PUT /api/v1/rules/{channel_id}` - Update channel rules

### Invite Settings
- `GET /api/v1/invite/settings` - Get settings
- `PUT /api/v1/invite/settings` - Update settings

### Utility
- `GET /api/v1/channels` - List all Slack channels
- `GET /api/v1/stats` - Dashboard statistics

## Usage

### Starting in HTTP Mode

**With Docker:**
```bash
docker compose up --build zebras-http
```

Then open **http://localhost:43117** in your browser.

**Without Docker:**
```bash
zebras http --port 43117
```

### Navigation
- Use the sidebar to navigate between sections
- Toggle sidebar visibility with the menu button
- Click on cards and rows for quick actions

### Tips
- All changes save automatically via the API
- Toast notifications appear in the top-right corner
- Use the search bars to filter large lists
- Hover over buttons to see tooltips

## Architecture

The new UI is a **lightweight single-page application (SPA)** that:
- Loads as a single static HTML file (`index.html`) with inline JavaScript (`app.js`)
- Uses Alpine.js for client-side state management and routing
- Fetches all data from RESTful API endpoints
- Has no server-side rendering or template processing
- Requires no build step or compilation
- Loads all dependencies from CDN (Tailwind, Alpine.js, Lucide icons)

This architecture provides:
- **Fast page loads** - No server-side rendering overhead
- **Responsive UI** - All interactions happen client-side
- **Simple deployment** - Just static files served by FastAPI
- **Easy development** - Edit HTML/JS and refresh browser

## Legacy UI

The old HTML form-based UI is still accessible at `/legacy` for backwards compatibility.

## Future Enhancements

Planned features:
- [ ] Activity log integration
- [ ] Real-time event monitoring
- [ ] Bulk operations for rules
- [ ] Export/import configuration
- [ ] Dark/light mode toggle
- [ ] User authentication
- [ ] Role-based access control
- [ ] Advanced analytics dashboard
- [ ] Rule testing interface

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Troubleshooting

### UI not loading?
1. Check that zebras-http is running: `docker compose ps`
2. Verify port 43117 is accessible: `curl http://localhost:43117/healthz`
3. Check logs: `docker compose logs zebras-http`

### API errors?
1. Open browser DevTools (F12)
2. Check Console for JavaScript errors
3. Check Network tab for failed requests
4. Verify database connection in logs

### Blank page?
1. Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
2. Clear browser cache
3. Check if JavaScript is enabled

---

Built with ❤️ for the ZaTech community
