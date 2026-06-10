#lang racket
(define (length s)
  (+ 1 (if (null? s)
     -1
     (length (cdr s))))
)

(define (contains s v)
  (if (null? s)
    false
    (if (= v (car s))
      true
      (contains (cdr s) v))))

(define (fib n)
  (define (fib-iter current k)
    (if (= k n)
      current
      (fib-iter (+ current
                   (fib (- k 1)))
                (+ k 1 ))))
      (if (= 1 n) 0 (fib-iter 1 2)))


(define (has-repeat s)
  (if (null? s)
    false
    (if (contains (cdr s) (car s))
      true
      (has-repeat (cdr s)))))



(define (reduce procedure s start)
  (if (null? s) start
  (reduce procedure
          (cdr s)
          (procedure start (car s)))))

(define (map procedure s)
  (if (null? s)
    '()
    (cons (procedure (car s))
          (map procedure (cdr s)))))

(define (rmap procedure s)
  (define (map-reverse s m)
    (if (null? s)
      m 
      (map-reverse (cdr s)
                   (cons (procedure (car s))
                         m))))
      (reverse (map-reverse s '())))

(define (reverse s)
  (define (reverse-iter s r)
    (if (null? s)
      r 
      (reverse-iter (cdr s)
                    (cons (car s) r ))))
  (reverse-iter s '()))
