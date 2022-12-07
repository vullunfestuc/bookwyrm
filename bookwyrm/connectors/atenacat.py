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
        born_date=lambda a:a.split('-')[0].rstrip().lstrip()
        died_date=lambda a:a.split('-')[1].rstrip().lstrip()
        self.book_mappings = [
            Mapping("id", remote_field="key", formatter=self.get_remote_id ),
            Mapping("title", remote_field="title" ),
            #Mapping("subtitle", remote_field="wdt:P1680", formatter=get_first),
            Mapping("description", remote_field="description"),
            Mapping("cover", remote_field="image", formatter=self.get_cover_url),
            Mapping("isbn13", remote_field="isbn", formatter=self.is_isbn13),
            Mapping("isbn10", remote_field="isbn",formatter=self.is_isbn10),
            #Mapping("languages", remote_field="wdt:P407", formatter=self.resolve_keys),
            Mapping("publishers", remote_field="publisher",formatter=self.get_publishers),
            Mapping("publishedDate", remote_field="publishing date"),
            #Mapping("pages", remote_field="wdt:P1104", formatter=get_first),
            Mapping("atenacatKey", remote_field="key" ),
        ] 

        self.author_mappings = [
            Mapping("id", remote_field="author", formatter=self.get_remote_id),
            Mapping("name", remote_field="author"),
            Mapping("born", remote_field="author dates", formatter=born_date),
            Mapping("died", remote_field="author dates", formatter=died_date),
        ] 

    def get_remote_id(self, value):
        """convert an id/uri into a url"""
        """be aware this is something as a fake. to obtain the data from a url"""
        return f"http://{self.identifier}/book?k={value}"
  
    def get_book_data(self, obj):
        
        realurl=obj.replace("http://"+self.identifier,self.base_url)
        params=realurl.split('?')[1]
        finalurl=realurl.split('?')[0]
        print("identifier:"+self.identifier+" and base url:"+self.base_url)
        print(obj+" and "+realurl)
        print("get book data from  "+finalurl +" and params "+params)
        extracted = get_data(finalurl,params)
        print(extracted)
        try:
            data = extracted
        except (KeyError, IndexError):
            raise ConnectorException("Invalid book data")
        
        #this is already a list of what we want.
        return data
        


    def get_remote_id_from_model(self, obj):
        """given the data stored, how can we look this up"""
        print("given the data stored, how can we look this up")
        return getattr(obj, getattr(self, "generated_remote_link_field"))

    def update_author_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing author"""
        remote_id = self.get_remote_id_from_model(obj)
        print("load the remote data from this connector and add it to an existing author")
        return self.get_or_create_author(remote_id, instance=obj)

    def update_book_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing book"""
        print("load the remote data from this connector and add it to an existing book")
        remote_id = self.get_remote_id_from_model(obj)
        data = self.get_book_data(remote_id)
        return self.create_edition_from_data(obj.parent_work, data, instance=obj)

    def is_work_data(self, data):
        """differentiate works and editions"""
        data["type"]="work"
        return True


    def get_edition_from_work_data(self, data):
        """every work needs at least one edition"""
        print("every work needs at least one edition ")
        if 'edition' not in data.keys():
            data['edition']=""
        return data

    def get_work_from_edition_data(self, data):
        """every edition needs a work"""
        return data

    # def myget_or_create_author(self, remote_id, instance=None):
    #     """load that author"""
    #     if not instance:
    #         existing = models.Author.find_existing_by_remote_id(remote_id)
    #         if existing:
    #             return existing
        

    #     mapped_data = self.dict_from_mappings(data, self.author_mappings)
    #     try:
    #         activity = activitypub.Author(**mapped_data)
    #     except activitypub.ActivitySerializerError:
    #         return None

    #     # this will dedupe
    #     return activity.to_model(
    #         model=models.Author, overwrite=False, instance=instance
    #     )


    def get_authors_from_data(self, data):
        """load author data"""
        authors=data.get("author")
        print("load author data")
        if type(authors) is list:
            for author in data.get("author"):
                authorurl=f"{self.base_url}/author?q={author}"
                yield self.get_or_create_author(authorurl)

        else:
            authorurl=f"{self.base_url}/author?q={authors}"
            yield self.get_or_create_author(authorurl)

    def get_publishers(self,publishers):
        if type(publishers) is list:
            return publishers
        else:
            return [publishers]       

    def is_isbn13(self,value):
        if len(value)==13:
            return value
        else:
            return None
    def is_isbn10(self,value):
        if len(value)==10:
            return value
        else:
            return None

    def get_data(url):

        print("get data in atena:"+str(url))
        return None

    def parse_search_data(self, data, min_confidence=1):
        for idx, search_result in enumerate(data):
            # build the remote id from the openlibrary key
            author = search_result.get("author") or ["Unknown"]
            view_link=f"http://cataleg.atena.biblioteques.cat/iii/encore/record/C__{search_result.get('key')}"
            key=self.get_remote_id(search_result.get("key") )
            yield SearchResult(
                title=search_result.get("title"),
                author=author,
                key=key,
                connector=self,
                year=search_result.get("year"),
                view_link=view_link,
             #   cover=cover,
            )

    def parse_isbn_search_data(self, data):
        for search_result in list(data.values()):
            # build the remote id from the openlibrary key
            authors = search_result.get("authors") or [{"name": "Unknown"}]
            author_names = [author.get("name") for author in authors]
            yield SearchResult(
                title=search_result.get("title"),
                author=", ".join(author_names),
                view_link=f"{self.base_url}/book?k={search_result.get('uri')}",
                connector=self,
                year=search_result.get("publish_date"),
            )

    def get_description(self,data):
        try:
            description=data['description']
        except:
            description=None
        return description
        
    def get_cover_url(self,data):
        return None

    def expand_book_data(self,book):
        """get more info on a book"""


    def get_atenacat_key(self,key):
        return key

