from typing import List

from http_request.request_details import RequestDetails
from http_request.request_runner import RequestRunner
from model.search_run_context import SearchRunContext
from model.search_tweets_task import SearchTweetsTask
from model.tweet import Tweet
from runner.request_details_builder import scrap_tweets_get_params, scrap_tweets_get_headers
from token_request import TokenRequest
from tweet_output.tweet_output import TweetOutput
from tweet_parser import TweetParser


class TweetSearchRunner:
    search_run_context: SearchRunContext
    search_tweets_task: SearchTweetsTask
    tweet_outputs: List[TweetOutput]
    return_scrapped_objects: bool

    def __init__(
            self,
            search_tweets_task: SearchTweetsTask,
            tweet_outputs: List[TweetOutput],
            search_run_context: SearchRunContext = SearchRunContext(),
            return_scrapped_objects: bool = False
    ):
        self.search_run_context = search_run_context
        self.search_tweets_task = search_tweets_task
        self.tweet_outputs = tweet_outputs
        self.return_scrapped_objects = return_scrapped_objects
        return

    def run(self):
        self._prepare_token()
        while not self._is_end_of_scrapping():
            self._execute_next_tweets_request()

    def _is_end_of_scrapping(self) -> bool:
        return self.search_run_context.last_tweets_download_count == 0 or \
               self.search_run_context.was_no_more_data_raised

    def _execute_next_tweets_request(self):
        request_params = self._get_next_request_details()
        response = RequestRunner.run_request(request_params)
        if response.is_token_expired():
            self._refresh_token()
        elif response.is_success():
            parsed_tweets = TweetParser.parse_tweets(response.text)
            self._process_new_tweets_to_output(parsed_tweets)
            self.search_run_context.scroll_token = TweetParser.parse_cursor(response.text)
            self.search_run_context.last_tweets_download_count = len(parsed_tweets)
            self.search_run_context.add_downloaded_tweets_count(len(parsed_tweets))
        else:
            # TODO add custom exception
            raise Exception('scrap exception ' + str(response))
        return

    def _get_next_request_details(self) -> RequestDetails:
        # TODO extract to external tool
        return RequestDetails(
            url='https://api.twitter.com/2/search/adaptive.json',
            headers=scrap_tweets_get_headers(self.search_run_context),
            params=scrap_tweets_get_params(self.search_run_context, self.search_tweets_task)
        )

    def _refresh_token(self):
        self.search_run_context.guest_auth_token = TokenRequest().refresh()
        return

    def _prepare_token(self):
        if self.search_run_context.guest_auth_token is None:
            self._refresh_token()
        return

    def _process_new_tweets_to_output(self, new_tweets: List[Tweet]):
        # TODO consider about error catching and return as part of running result
        for tweet_output in self.tweet_outputs:
            tweet_output.export_tweets(new_tweets)
        return