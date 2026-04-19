class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response


class YearEndCarryForwardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from App.services.year_end_service import run_year_end_carry_forward_if_due

        try:
            run_year_end_carry_forward_if_due()
        except Exception:
            # Never block user traffic because of automatic rollover work.
            pass

        return self.get_response(request)
