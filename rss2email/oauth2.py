# Copyright (C) 2024 Arun Persaud <apersaud@lbl.gov>
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"""
Enable OAuth2 for gmail.

Most likely this can also work for other oauth2 providers with minor modifications.

The file provides two functions:
* get_oauth2_auth_string: this is used in email.py to log into gmail using oauth2
* get_refresh_token: get a refresh token only needs to be called once.
"""

import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request


def get_oauth2_auth_string(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    username: str,
    request_url: str = "https://accounts.google.com",
) -> str:
    """Create a string with an oauth2 access token.

    This make a request to the oauth2 provider to get an access token
    and then formats this correctly to be used to authenticate an IMAP instance.
    """

    parameters = {}
    parameters["client_id"] = client_id
    parameters["client_secret"] = client_secret
    parameters["refresh_token"] = refresh_token
    parameters["grant_type"] = "refresh_token"

    response = urllib.request.urlopen(
        f"{request_url}/o/oauth2/token",
        urllib.parse.urlencode(parameters).encode("utf-8"),
    ).read()
    response = json.loads(response)

    access_token = response["access_token"]

    auth_string = f"user={username}\1auth=Bearer {access_token}\1\1"

    return auth_string


def get_refresh_token(
    client_id: str,
    client_secret: str,
    request_url: str = "https://accounts.google.com",
    scope: str = "https://mail.google.com/",
) -> None:
    """Create a reusable oauth2 refresh token.

    Makes two requests to the oauth2 provider to generate a refresh token.

    Refresh tokens are then used to generate authorization tockens for
    every login attempt.

    """
    parameters = {}
    parameters["client_id"] = client_id
    parameters["redirect_uri"] = "http://localhost_error/"
    parameters["prompt"] = "consent"
    parameters["scope"] = scope
    parameters["access_type"] = "offline"
    parameters["response_type"] = "code"

    parameter_list = []
    for param in sorted(parameters.items(), key=lambda x: x[0]):
        escaped_param = urllib.parse.quote(param[1], safe="~-._")
        parameter_list.append(f"{param[0]}={escaped_param}")
    parameter_str = "&".join(parameter_list)

    authorize_url = f"{request_url}/o/oauth2/auth?{parameter_str}"

    print("To get a refresh token, follow this link:")
    print(f"  {authorize_url}")
    print(
        "Once you allowed access to your email via oauth2, you will be redirected to a new webpage. The redirect will not work!"
    )
    print(
        "However, the url will include the needed verification code for the next step.\n"
        "Copy the whole URL out of the browser and paste below"
    )
    tmp = input("Enter failed URL: ")

    # add error checking
    tmp = tmp.split("code=")[1]
    authorization_code = tmp.split("&scope")[0]

    parameters = {}
    parameters["client_id"] = client_id
    parameters["client_secret"] = client_secret
    parameters["code"] = authorization_code
    parameters["redirect_uri"] = "http://localhost/"
    parameters["grant_type"] = "authorization_code"

    response = urllib.request.urlopen(
        f"{request_url}/o/oauth2/token",
        urllib.parse.urlencode(parameters).encode("utf-8"),
    ).read()

    response = json.loads(response)
    print(f"Refresh Token: {response['refresh_token']}")
