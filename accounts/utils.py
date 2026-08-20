def get_client_ip(request):
    cf_connecting_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()
    return request.META.get("REMOTE_ADDR")
