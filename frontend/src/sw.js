import {clientsClaim} from 'workbox-core'
import {cleanupOutdatedCaches, precacheAndRoute, createHandlerBoundToURL} from 'workbox-precaching'
import {NavigationRoute, registerRoute} from 'workbox-routing'

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), {
  allowlist: [/^\/$/, /^\/app(?:\/[^?]*)?(?:\?.*)?$/, /^\/(?:connexion|commencer)(?:\?.*)?$/],
  denylist: [/^\/api\//, /^\/django-admin/],
}))
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting()
})
clientsClaim()
