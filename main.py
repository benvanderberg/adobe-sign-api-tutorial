import os
import time
from functools import cache
import requests
from flask import Flask, render_template, request, url_for
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)


def sign_validate(resp, code=200):
    """
    An overly simplistic validator for Sign API responses.

    In a production environment, you'll want this to be MUCH more sophisticated.
    """
    if resp.status_code != code:
        raise Exception(
            {
                "issue": "Bad Response",
                "status_code": resp.status_code,
                "data": resp.text,
            }
        )


@cache
def headers():
    """
    Basic helper for generating headers w/ a valid integration key embedded.
    """
    #  Grab the integration key from the env
    token = os.getenv("INTEGRATION_KEY")
    return {"Authorization": f"Bearer {token}"}


@cache
def base():
    """
    Use the baseUris call to retrieve the api access point.

    In practice, with an integration key, this value can be stored as an env.
    """
    # Send request
    url = "https://api.na1.echosign.com:443/api/rest/v6/baseUris"
    resp = requests.get(url, headers=headers())

    # Validate
    sign_validate(resp)

    data = resp.json()
    return data["apiAccessPoint"]


# ##############################################################################
# HTML
# ##############################################################################


@app.route("/")
def index():
    return render_template("index.html", action="/submitted", method="POST", email=True)


@app.route("/submitted", methods=["POST"])
def submitted():
    data = dict(request.form)
    app.logger.debug(data)
    return render_template("submitted.html", data=data)


# ##############################################################################
# WEBFORM
# ##############################################################################


@app.route("/webform")
def webform_index():
    """
    Send request to page with a widget on it.

    We're including the values in a query string, so that we may generate an
    iframe the pre-populates form fields.

    Since the webform requires an email to be user entered, we're removing it
    from the form.
    """
    return render_template(
        "index.html", action="/webform/sign", method="GET", email=False
    )


@app.route("/webform/sign", methods=["GET"])
def webform_sign():
    """
    Embed a web form into an iframe.

    We are also taking the query string and interpolating it into the webform
    url in such a way that it'll pre-populate data.
    """
    url = os.getenv("WAIVER_WEBFORM")
    app.logger.debug(url)

    # Build webform URL
    # https://{base}/public/esignWidget?wid={id}#{field1}={v1}&{field2}={v2}
    data = dict(request.args)
    if data:
        params = []
        for key, val in data.items():
            params.append(f"{key}={val}")
        query = "&".join(params)
        url = f"{url}#{query}"
    app.logger.debug(url)

    return render_template("sign.html", url=url)


# ##############################################################################
# Send
# ##############################################################################


@app.route("/send")
def send_index():
    """
    Nothing fancy here, just a form that sends post data.
    """
    return render_template(
        "index.html", action="/send/submitted", method="POST", email=True
    )


@app.route("/send/submitted", methods=["POST"])
def send_submitted():
    """
    Generate an agreement & respond w/ a pretty website that has things.
    """
    data = dict(request.form)
    app.logger.debug(data)

    # Build URL
    url = f"{base()}api/rest/v6/agreements"

    # Payload
    req = {
        "fileInfos": [{"libraryDocumentId": os.getenv("WAIVER_TEMPLATE")}],
        "name": "Waiver",
        "participantSetsInfo": [
            {
                "memberInfos": [{"email": data.get("email")}],
                "order": 1,
                "role": "SIGNER",
            },
            {
                "memberInfos": [{"email": os.getenv("ADMIN")}],
                "order": 2,
                "role": "SIGNER",
            },
        ],
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
        "mergeFieldInfo": [
            {"fieldName": "firstName", "defaultValue": data.get("firstName")},
            {"fieldName": "lastName", "defaultValue": data.get("lastName")},
        ],
    }

    # Send request
    resp = requests.post(url, headers=headers(), json=req)

    # Validate
    sign_validate(resp, code=201)

    return render_template("submitted.html", data=resp.json())


# ##############################################################################
# Embed
# ##############################################################################


@app.route("/embed")
def embed_index():
    return render_template(
        "index.html", action="/embed/sign", method="POST", email=True
    )


@app.route("/embed/sign", methods=["POST"])
def embed_sign():
    data = dict(request.form)
    app.logger.debug(data)

    # Build URL
    url = f"{base()}api/rest/v6/agreements"

    # Payload
    req = {
        "fileInfos": [{"libraryDocumentId": os.getenv("WAIVER_TEMPLATE")}],
        "name": "Waiver",
        "participantSetsInfo": [
            {
                "memberInfos": [{"email": data.get("email")}],
                "order": 1,
                "role": "SIGNER",
            },
            {
                "memberInfos": [{"email": os.getenv("ADMIN")}],
                "order": 2,
                "role": "SIGNER",
            },
        ],
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
        "mergeFieldInfo": [
            {"fieldName": "firstName", "defaultValue": data.get("firstName")},
            {"fieldName": "lastName", "defaultValue": data.get("lastName")},
        ],
        # New Stuff
        "emailOption": {
            "sendOptions": {
                "initEmails": "NONE",
            }
        },
        "postSignOption": {
            "redirectDelay": 0,
            "redirectUrl": url_for("embed_submitted", _external=True),
        },
    }

    # Send request
    resp = requests.post(url, headers=headers(), json=req)
    sign_validate(resp, code=201)

    # We are waiting for async processes to complete...
    # This is NOT best practice!!!  DO NOT do this in production
    # A better way would be to use a retry loop
    time.sleep(3)

    #  Get the new agreement id
    agreement_data = resp.json()
    agreement_id = agreement_data["id"]

    # Build embed URL
    embed_url = f"{base()}api/rest/v6/agreements/{agreement_id}/signingUrls"

    # Get Signing URL
    embed_resp = requests.get(embed_url, headers=headers())
    sign_validate(embed_resp)

    # Extract URL
    embed_data = embed_resp.json()
    signing_url = embed_data["signingUrlSetInfos"][0]["signingUrls"][0]["esignUrl"]

    return render_template("sign.html", url=signing_url)


@app.route("/embed/submitted", methods=["GET"])
def embed_submitted():
    return f"<h2>Successfully submitted</h2>"
