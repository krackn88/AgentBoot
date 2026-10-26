using System;
using System.Collections.Generic;
using LiteDB;
using RuriLib.Interfaces;
using RuriLib.Models;

namespace OpenBullet.Linux.Repositories;

public sealed class LiteDbRepository<T> : IRepository<T, Guid> where T : Persistable<Guid>
{
    private readonly string _connectionString;
    private readonly string _collection;

    public LiteDbRepository(string connectionString, string collection)
    {
        _connectionString = connectionString;
        _collection = collection;
    }

    public void Add(T entity) => WithDb(coll => coll.Insert(entity));

    public void Add(IEnumerable<T> entities) => WithDb(coll => coll.InsertBulk(entities));

    public IEnumerable<T> Get() => WithDb(coll => coll.FindAll());

    public T Get(Guid id) => WithDb(coll => coll.FindById(id));

    public void Remove(T entity) => WithDb(coll => coll.Delete(entity.Id));

    public void Remove(IEnumerable<T> entities)
    {
        WithDb(coll =>
        {
            foreach (var entity in entities)
                coll.Delete(entity.Id);
        });
    }

    public void RemoveAll()
    {
        using var db = new LiteDatabase(_connectionString);
        db.DropCollection(_collection);
    }

    public void Update(T entity) => WithDb(coll => coll.Update(entity));

    public void Update(IEnumerable<T> entities) => WithDb(coll => coll.Update(entities));

    private void WithDb(Action<LiteCollection<T>> action)
    {
        using var db = new LiteDatabase(_connectionString);
        action(db.GetCollection<T>(_collection));
    }

    private TResult WithDb<TResult>(Func<LiteCollection<T>, TResult> func)
    {
        using var db = new LiteDatabase(_connectionString);
        return func(db.GetCollection<T>(_collection));
    }
}
