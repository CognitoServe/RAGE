class KnowledgeError(Exception):
    pass


class FactNotFoundError(KnowledgeError):
    pass


class DuplicateFactError(KnowledgeError):
    pass
