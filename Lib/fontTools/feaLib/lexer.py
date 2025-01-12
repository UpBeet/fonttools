from __future__ import print_function, division, absolute_import
from __future__ import unicode_literals
from fontTools.feaLib.error import FeatureLibError
import codecs
import re
import os


class Lexer(object):
    NUMBER = "NUMBER"
    STRING = "STRING"
    NAME = "NAME"
    FILENAME = "FILENAME"
    GLYPHCLASS = "GLYPHCLASS"
    CID = "CID"
    SYMBOL = "SYMBOL"
    COMMENT = "COMMENT"
    NEWLINE = "NEWLINE"

    CHAR_WHITESPACE_ = " \t"
    CHAR_NEWLINE_ = "\r\n"
    CHAR_SYMBOL_ = ";:-+'{}[]<>()="
    CHAR_DIGIT_ = "0123456789"
    CHAR_HEXDIGIT_ = "0123456789ABCDEFabcdef"
    CHAR_LETTER_ = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    CHAR_NAME_START_ = CHAR_LETTER_ + "_+*:.^~!\\"
    CHAR_NAME_CONTINUATION_ = CHAR_LETTER_ + CHAR_DIGIT_ + "_.+*:^~!"

    RE_GLYPHCLASS = re.compile(r"^[A-Za-z_0-9.]+$")

    MODE_NORMAL_ = "NORMAL"
    MODE_FILENAME_ = "FILENAME"

    def __init__(self, text, filename):
        self.filename_ = filename
        self.line_ = 1
        self.pos_ = 0
        self.line_start_ = 0
        self.text_ = text
        self.text_length_ = len(text)
        self.mode_ = Lexer.MODE_NORMAL_

    def __iter__(self):
        return self

    def next(self):  # Python 2
        return self.__next__()

    def __next__(self):  # Python 3
        while True:
            token_type, token, location = self.next_()
            if token_type not in {Lexer.COMMENT, Lexer.NEWLINE}:
                return (token_type, token, location)

    def next_(self):
        self.scan_over_(Lexer.CHAR_WHITESPACE_)
        column = self.pos_ - self.line_start_ + 1
        location = (self.filename_, self.line_, column)
        start = self.pos_
        text = self.text_
        limit = len(text)
        if start >= limit:
            raise StopIteration()
        cur_char = text[start]
        next_char = text[start + 1] if start + 1 < limit else None

        if cur_char == "\n":
            self.pos_ += 1
            self.line_ += 1
            self.line_start_ = self.pos_
            return (Lexer.NEWLINE, None, location)
        if cur_char == "\r":
            self.pos_ += (2 if next_char == "\n" else 1)
            self.line_ += 1
            self.line_start_ = self.pos_
            return (Lexer.NEWLINE, None, location)
        if cur_char == "#":
            self.scan_until_(Lexer.CHAR_NEWLINE_)
            return (Lexer.COMMENT, text[start:self.pos_], location)

        if self.mode_ is Lexer.MODE_FILENAME_:
            if cur_char != "(":
                raise FeatureLibError("Expected '(' before file name",
                                      location)
            self.scan_until_(")")
            cur_char = text[self.pos_] if self.pos_ < limit else None
            if cur_char != ")":
                raise FeatureLibError("Expected ')' after file name",
                                      location)
            self.pos_ += 1
            self.mode_ = Lexer.MODE_NORMAL_
            return (Lexer.FILENAME, text[start + 1:self.pos_ - 1], location)

        if cur_char == "\\" and next_char in Lexer.CHAR_DIGIT_:
            self.pos_ += 1
            self.scan_over_(Lexer.CHAR_DIGIT_)
            return (Lexer.CID, int(text[start + 1:self.pos_], 10), location)
        if cur_char == "@":
            self.pos_ += 1
            self.scan_over_(Lexer.CHAR_NAME_CONTINUATION_)
            glyphclass = text[start + 1:self.pos_]
            if len(glyphclass) < 1:
                raise FeatureLibError("Expected glyph class name", location)
            if len(glyphclass) > 30:
                raise FeatureLibError(
                    "Glyph class names must not be longer than 30 characters",
                    location)
            if not Lexer.RE_GLYPHCLASS.match(glyphclass):
                raise FeatureLibError(
                    "Glyph class names must consist of letters, digits, "
                    "underscore, or period", location)
            return (Lexer.GLYPHCLASS, glyphclass, location)
        if cur_char in Lexer.CHAR_NAME_START_:
            self.pos_ += 1
            self.scan_over_(Lexer.CHAR_NAME_CONTINUATION_)
            token = text[start:self.pos_]
            if token == "include":
                self.mode_ = Lexer.MODE_FILENAME_
            return (Lexer.NAME, token, location)
        if cur_char == "0" and next_char in "xX":
            self.pos_ += 2
            self.scan_over_(Lexer.CHAR_HEXDIGIT_)
            return (Lexer.NUMBER, int(text[start:self.pos_], 16), location)
        if cur_char in Lexer.CHAR_DIGIT_:
            self.scan_over_(Lexer.CHAR_DIGIT_)
            return (Lexer.NUMBER, int(text[start:self.pos_], 10), location)
        if cur_char == "-" and next_char in Lexer.CHAR_DIGIT_:
            self.pos_ += 1
            self.scan_over_(Lexer.CHAR_DIGIT_)
            return (Lexer.NUMBER, int(text[start:self.pos_], 10), location)
        if cur_char in Lexer.CHAR_SYMBOL_:
            self.pos_ += 1
            return (Lexer.SYMBOL, cur_char, location)
        if cur_char == '"':
            self.pos_ += 1
            self.scan_until_('"\r\n')
            if self.pos_ < self.text_length_ and self.text_[self.pos_] == '"':
                self.pos_ += 1
                return (Lexer.STRING, text[start + 1:self.pos_ - 1], location)
            else:
                raise FeatureLibError("Expected '\"' to terminate string",
                                      location)
        raise FeatureLibError("Unexpected character: '%s'" % cur_char,
                              location)

    def scan_over_(self, valid):
        p = self.pos_
        while p < self.text_length_ and self.text_[p] in valid:
            p += 1
        self.pos_ = p

    def scan_until_(self, stop_at):
        p = self.pos_
        while p < self.text_length_ and self.text_[p] not in stop_at:
            p += 1
        self.pos_ = p


class IncludingLexer(object):
    def __init__(self, filename):
        self.lexers_ = [self.make_lexer_(filename, (filename, 0, 0))]

    def __iter__(self):
        return self

    def next(self):  # Python 2
        return self.__next__()

    def __next__(self):  # Python 3
        while self.lexers_:
            lexer = self.lexers_[-1]
            try:
                token_type, token, location = lexer.next()
            except StopIteration:
                self.lexers_.pop()
                continue
            if token_type is Lexer.NAME and token == "include":
                fname_type, fname_token, fname_location = lexer.next()
                if fname_type is not Lexer.FILENAME:
                    raise FeatureLibError("Expected file name", fname_location)
                semi_type, semi_token, semi_location = lexer.next()
                if semi_type is not Lexer.SYMBOL or semi_token != ";":
                    raise FeatureLibError("Expected ';'", semi_location)
                curpath, _ = os.path.split(lexer.filename_)
                path = os.path.join(curpath, fname_token)
                if len(self.lexers_) >= 5:
                    raise FeatureLibError("Too many recursive includes",
                                          fname_location)
                self.lexers_.append(self.make_lexer_(path, fname_location))
                continue
            else:
                return (token_type, token, location)
        raise StopIteration()

    @staticmethod
    def make_lexer_(filename, location):
        try:
            with codecs.open(filename, "rb", "utf-8") as f:
                return Lexer(f.read(), filename)
        except IOError as err:
            raise FeatureLibError(str(err), location)
