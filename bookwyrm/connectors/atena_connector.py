""" atenaCat my own data connector """
from bookwyrm import models
from bookwyrm.book_search import SearchResult
from .abstract_connector import AbstractConnector, Mapping
from .abstract_connector import get_data
from .connector_manager import ConnectorException, create_edition_task


class Connector(AbstractConnector):
    """generic book data connector"""

    def __init__(self, identifier):
        super().__init__(identifier)
        # fields we want to look for in book data to copy over
        # title we handle separately.
        get_first = lambda a: a[0]
        self.book_mappings = [
            Mapping("title", remote_field="title", formatter=get_first),
            Mapping("subtitle", remote_field="wdt:P1680", formatter=get_first),
            Mapping(
                "description", remote_field="sitelinks", formatter=self.get_description
            ),
            Mapping("cover", remote_field="image", formatter=self.get_cover_url),
            Mapping("isbn13", remote_field="wdt:P212", formatter=get_first),
            Mapping("isbn10", remote_field="wdt:P957", formatter=get_first),
            Mapping("languages", remote_field="wdt:P407", formatter=self.resolve_keys),
            Mapping("publishers", remote_field="wdt:P123", formatter=self.resolve_keys),
            Mapping("publishedDate", remote_field="wdt:P577", formatter=get_first),
            Mapping("pages", remote_field="wdt:P1104", formatter=get_first),
        ] 

        self.author_mappings = [
            Mapping("id", remote_field="uri", formatter=self.get_remote_id),
            Mapping("name", remote_field="labels", formatter=get_language_code),
            Mapping("born", remote_field="wdt:P569", formatter=get_first),
            Mapping("died", remote_field="wdt:P570", formatter=get_first),
        ] 

    def get_remote_id(self, value):
        """convert an id/uri into a url"""
        return f"{self.books_url}/search?q={value}"
  
    def get_book_data(self, obj):
        extracted = get_data(obj)
        try:
            data = extracted[0]
        except (KeyError, IndexError):
            raise ConnectorException("Invalid book data")
        
        #this is already a list of what we want.
        return data
        


    def get_remote_id_from_model(self, obj):
        """given the data stored, how can we look this up"""
        return getattr(obj, getattr(self, "generated_remote_link_field"))

    def update_author_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing author"""
        remote_id = self.get_remote_id_from_model(obj)
        return self.get_or_create_author(remote_id, instance=obj)

    def update_book_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing book"""
        remote_id = self.get_remote_id_from_model(obj)
        data = self.get_book_data(remote_id)
        return self.create_edition_from_data(obj.parent_work, data, instance=obj)

    def is_work_data(self, data):
        """differentiate works and editions"""

    def get_edition_from_work_data(self, data):
        """every work needs at least one edition"""

    def get_work_from_edition_data(self, data):
        """every edition needs a work"""

    def get_authors_from_data(self, data):
        for author_blob in data.get("author", []):
            author_blob = author_blob.get("author", author_blob)
            # this id is "/authors/OL1234567A"
            author_id = author_blob["key"]
            url = f"{self.base_url}{author_id}"
            author = self.get_or_create_author(url)
            if not author:
                continue
            yield author
        """load author data"""

    def expand_book_data(self, book):
        """get more info on a book"""
