"""En-têtes navigateur. Auteur : Jonathan Kakesa (JonathanK-N)."""
class SecurityHeaders:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        if not request.path.startswith('/django-admin/'):
            response['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        response['Permissions-Policy']='camera=(), microphone=(), geolocation=(self)'
        if request.path.startswith('/api/v2/') or 'invitation' in request.GET:response['Referrer-Policy']='no-referrer'
        from django.core.handlers.asgi import ASGIRequest
        if isinstance(request,ASGIRequest) and response.streaming and not response.is_async:
            import asyncio
            original=response.streaming_content
            async def chunks():
                iterator=iter(original)
                while True:
                    chunk=await asyncio.to_thread(next,iterator,None)
                    if chunk is None:break
                    yield chunk
            response.streaming_content=chunks()
        return response
