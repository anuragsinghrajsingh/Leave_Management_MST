self.addEventListener("push", function (event) {
    let payload = {};
    if (event.data) {
        try {
            payload = event.data.json();
        } catch (error) {
            payload = { title: "Leave Management", body: event.data.text() };
        }
    }

    const title = payload.title || "Leave Management";
    const options = {
        body: payload.body || "You have a new update.",
        icon: payload.icon || "/static/images/ms-technology-logo.png",
        badge: payload.badge || payload.icon || "/static/images/ms-technology-logo.png",
        tag: payload.tag || "leave-management-update",
        data: {
            url: payload.url || "/",
            kind: payload.kind || "general",
        },
        renotify: true,
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    const targetUrl = new URL(event.notification.data && event.notification.data.url || "/", self.location.origin).href;

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
            for (const client of clientList) {
                if (client.url === targetUrl && "focus" in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
            return null;
        })
    );
});
