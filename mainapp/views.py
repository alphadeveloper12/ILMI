from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from mainapp.helpers import (
    genre_wise,
    tfidf_recommendations,
    get_book_dict,
    get_rated_bookids,
    combine_ids,
    embedding_recommendations,
    get_top_n,
    popular_among_users,
)
from mainapp.models import UserRating, SaveForLater
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render
from django.http import HttpResponse
from PyPDF2 import PdfReader
import os
from django.conf import settings
from django.http import FileResponse
import tempfile
import pyttsx3
from .models import Book
from gtts import gTTS
import os
from django.conf import settings
from django.http import FileResponse

import random
import operator


@ensure_csrf_cookie
def index(request):
    """
    View to render Homepage
    """
    books = popular_among_users()
    return render(request, "mainapp/index.html", {"books": books})


@ensure_csrf_cookie
def genre_books(request, genre):
    """
    View to render Books in a particular genre
    """
    genre_topbooks = genre_wise(genre)
    genre_topbooks = genre_topbooks.to_dict("records")
    context = {
        "genre": genre.capitalize(),
        "genre_topbook": genre_topbooks,
    }
    return render(request, "mainapp/genre.html", context)


@ensure_csrf_cookie
def explore_books(request):
    """
    View to Render Explore Page
    Renders Top N Books
    """
    N = 152
    sample = get_top_n().sample(N).to_dict("records")
    return render(request, "mainapp/explore.html", {"book": sample})


@login_required
@ensure_csrf_cookie
def book_recommendations(request):
    """
    View to render book recommendations

    Count Vectorizer Approach:
        1. Get Ratings of User
        2. Shuffle by Top Ratings(For Randomness each time)
        3. Recommend according to Top Rated Book
    """
    user_ratings = list(
        UserRating.objects.filter(user=request.user).order_by("-bookrating")
    )
    random.shuffle(user_ratings)
    best_user_ratings = sorted(
        user_ratings, key=operator.attrgetter("bookrating"), reverse=True
    )

    if len(best_user_ratings) < 4:
        messages.info(request, "Please rate atleast 5 books")
        return redirect("index")
    if best_user_ratings:
        # If one or more book is rated
        bookid = best_user_ratings[0].bookid
        already_rated_books = get_rated_bookids(user_ratings)
        # Get bookids based on TF-IDF weighing
        tfidf_bookids = set(tfidf_recommendations(bookid))

        # Shuffle again for randomness for second approach
        random.shuffle(user_ratings)
        best_user_ratings = sorted(
            user_ratings, key=operator.attrgetter("bookrating"), reverse=True
        )
        # Get Top 10 bookids based on embedding
        embedding_bookids = set(embedding_recommendations(best_user_ratings))

        best_bookids = combine_ids(
            tfidf_bookids, embedding_bookids, already_rated_books
        )
        all_books_dict = get_book_dict(best_bookids)
    else:
        return redirect("index")
    return render(request, "mainapp/recommendation.html", {"books": all_books_dict})


@login_required
@ensure_csrf_cookie
def read_books(request):
    """View To Render Library Page"""
    user_ratings = list(
        UserRating.objects.filter(user=request.user).order_by("-bookrating")
    )
    if len(user_ratings) == 0:
        messages.info(request, "Please rate some books")
        return redirect("index")
    if user_ratings:
        rated_books = set(get_rated_bookids(user_ratings))
        books = get_book_dict(rated_books)
        num = len(books)
        # Add pagination to the page showing 10 books
        paginator = Paginator(books, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
    else:
        return redirect("index")
    return render(request, "mainapp/read.html", {"page_obj": page_obj, "num": num})


def handler404(request, *args, **argv):
    response = render(request, "mainapp/error_handler.html")
    response.status_code = 404
    return response


def handler500(request, *args, **argv):
    response = render(request, "mainapp/error_handler.html")
    response.status_code = 500
    return response


def SaveList(request):
    """View to render Saved books page"""
    user_ratings = list(
        UserRating.objects.filter(user=request.user).order_by("-bookrating")
    )
    rated_books = set(get_rated_bookids(user_ratings))
    book = set(
        SaveForLater.objects.filter(user=request.user).values_list("bookid", flat=True)
    )
    book_id = list(book)
    for i in range(len(book_id)):
        if book_id[i] in rated_books:
            saved_book = SaveForLater.objects.filter(
                user=request.user, bookid=book_id[i]
            )
            saved_book.delete()
            book_id.remove(book_id[i])
    if len(book_id) == 0:
        messages.info(request, "Please Add Some Books")
        return redirect("index")
    books = get_book_dict(book_id)
    total_books = len(books)
    paginator = Paginator(books, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request, "mainapp/saved_book.html", {"page_obj": page_obj, "num": total_books}
    )

from .models import Book
@login_required
@ensure_csrf_cookie
def listen(request):
    """View To Render Library Page"""
    books = Book.objects.all()
    num = books.count()

    if num > 0:
        # Add pagination to the page showing 10 books
        paginator = Paginator(books, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
    else:
        no_books_available = True
        return render(request, "mainapp/listen.html", {"no_books_available": no_books_available})

    return render(request, "mainapp/listen.html", {"page_obj": page_obj, "num": num})


def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as f:
        pdf = PdfReader(f)
        text = ''
        for page in pdf.pages:
            text += page.extract_text()
        return text


from django.conf import settings
from django.http import HttpResponse

def text_to_speech(request, book_id):
    book = Book.objects.get(pk=book_id)
    pdf_path = book.pdf_file.path
    pdf_text = extract_text_from_pdf(pdf_path)

    # Generate the audio file path
    audio_file_path = os.path.join(settings.MEDIA_ROOT, 'audio', f'{book.bookname}.mp3')
    print(audio_file_path)

    # Check if the audio file already exists
    if os.path.exists(audio_file_path):
        # Serve the existing audio file to the user
        with open(audio_file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='audio/mp3')
            response['Content-Disposition'] = f'inline; filename="{book.bookname}.mp3"'
            # print(response)
            # Get the relative path of the audio file
            audio_file_relative_path = os.path.join('audio', f'{book.bookname}.mp3')
            print(audio_file_path)

            # Construct the direct URL of the audio file
            audio_file_url = f'{settings.MEDIA_URL}{audio_file_relative_path}'
            print(audio_file_path)

            # Return the direct URL in the response header
            response['X-Audio-File-URL'] = audio_file_url
            print(response)
            return response
    else:
        # Convert text to speech using gTTS library
        tts = gTTS(text=pdf_text, lang='en')

        # Save the audio file
        tts.save(audio_file_path)

        # Serve the newly created audio file to the user
        with open(audio_file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='audio/mp3')
            response['Content-Disposition'] = f'inline; filename="{book.bookname}.mp3"'

        # Get the relative path of the audio file
        audio_file_relative_path = os.path.join('audio', f'{book.bookname}.mp3')
        print(audio_file_path)

        # Construct the direct URL of the audio file
        audio_file_url = f'{settings.MEDIA_URL}{audio_file_relative_path}'
        print(audio_file_path)

        # Return the direct URL in the response header
        response['X-Audio-File-URL'] = audio_file_url
        print(response)
        return response
