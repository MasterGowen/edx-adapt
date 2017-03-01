"""
General Resources for all API resources modules
"""
from flask_restful import Resource


class BaseResource(Resource):
    def __init__(self, **kwargs):
        self.repo = kwargs['data']  # repo: DataInterface
        self.selector = kwargs['selector']  # selector: SelectInterface
